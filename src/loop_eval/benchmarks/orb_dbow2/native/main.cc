// Standalone retrieval: no tracking, map, covisibility, or correction objects.
#include "common.h"
#include "sophus/se3.hpp"
#include <chrono>
#include <algorithm>
#include <iostream>
#include <cstdlib>

using Clock = std::chrono::steady_clock;
double ms(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double,std::milli>(b-a).count();
}

struct Calibration {
    cv::Mat x,y,xright,yright;
    cv::Size size;
    explicit Calibration(cv::FileStorage& f) {
        if(std::string(f["Camera.type"]) != "PinHole" || std::string(f["File.version"]) != "1.0")
            throw std::runtime_error("Only pinned EuRoC PinHole settings are supported");
        if(!f["Camera.newWidth"].empty() || !f["Camera.newHeight"].empty())
            throw std::runtime_error("Resize settings are unsupported");
        size = cv::Size(int(f["Camera.width"]), int(f["Camera.height"]));
        auto K = [&](std::string name) {
            cv::Mat k=(cv::Mat_<float>(3,3) << float(f[name+".fx"]),0,float(f[name+".cx"]),0,float(f[name+".fy"]),float(f[name+".cy"]),0,0,1);
            k.convertTo(k,CV_64F); return k;
        };
        cv::Mat d=(cv::Mat_<float>(4,1) << float(f["Camera1.k1"]),float(f["Camera1.k2"]),float(f["Camera1.p1"]),float(f["Camera1.p2"]));
        cv::Mat t; f["Stereo.T_c1_c2"] >> t;
        Eigen::Matrix3f r; Eigen::Vector3f v;
        for(int i=0;i<3;++i) {v(i)=t.at<float>(i,3); for(int j=0;j<3;++j) r(i,j)=t.at<float>(i,j);}
        auto inverse=Sophus::SE3f(Eigen::Quaternionf(r),v).inverse().matrix3x4();
        cv::Mat rotation(3,3,CV_64F),translation(3,1,CV_64F);
        for(int i=0;i<3;++i) {translation.at<double>(i)=inverse(i,3); for(int j=0;j<3;++j) rotation.at<double>(i,j)=inverse(i,j);}
        cv::Mat r1,r2,p1,p2,q;
        // Pinned Settings::camera2DistortionCoef returns camera1 coefficients.
        // Match that upstream behavior exactly; reference test guards parity.
        cv::stereoRectify(K("Camera1"),d,K("Camera2"),d,size,rotation,translation,r1,r2,p1,p2,q,cv::CALIB_ZERO_DISPARITY,-1,size);
        cv::initUndistortRectifyMap(K("Camera1"),d,r1,p1(cv::Rect(0,0,3,3)),size,CV_32F,x,y);
        cv::initUndistortRectifyMap(K("Camera2"),d,r2,p2(cv::Rect(0,0,3,3)),size,CV_32F,xright,yright);
    }
};

int main(int argc, char** argv) {
    try {
        if(argc != 6 && argc != 7) throw std::runtime_error("Usage: orb_dbow2 vocabulary settings replay.tsv exclusion_ns top_k [dump_prefix]");
        cv::setNumThreads(1);
        const long long exclusion=std::stoll(argv[4]); const int k=std::stoi(argv[5]);
        if(exclusion<=0 || k<1) throw std::runtime_error("Invalid retrieval policy");
        cv::FileStorage f(argv[2],cv::FileStorage::READ);
        if(!f.isOpened()) throw std::runtime_error("Cannot open settings");
        Calibration calibration(f);
        ORB_SLAM3::ORBextractor extractor{int(f["ORBextractor.nFeatures"]),float(f["ORBextractor.scaleFactor"]),int(f["ORBextractor.nLevels"]),int(f["ORBextractor.iniThFAST"]),int(f["ORBextractor.minThFAST"])};
        ORB_SLAM3::ORBextractor rightExtractor{int(f["ORBextractor.nFeatures"]),float(f["ORBextractor.scaleFactor"]),int(f["ORBextractor.nLevels"]),int(f["ORBextractor.iniThFAST"]),int(f["ORBextractor.minThFAST"])};
        const char* featureDirectory=std::getenv("LDO_ORB_FEATURE_DIR");
        ORB_SLAM3::ORBVocabulary vocabulary;
        if(!vocabulary.loadFromTextFile(argv[1])) throw std::runtime_error("Cannot load vocabulary");
        std::ifstream replay(argv[3]); if(!replay) throw std::runtime_error("Cannot open replay");
        struct Entry {long long stamp; DBoW2::BowVector bow;}; std::vector<Entry> history;
        std::string line; long long previous=-1;
        std::cout << std::setprecision(17);
        while(std::getline(replay,line)) {
            auto tab=line.find('\t'); if(tab==std::string::npos) throw std::runtime_error("Invalid replay row");
            long long stamp=std::stoll(line.substr(0,tab));
            if(stamp<=previous) throw std::runtime_error("Nonchronological replay"); previous=stamp;
            auto start=Clock::now(); cv::Mat raw=cv::imread(line.substr(tab+1),cv::IMREAD_UNCHANGED),image;
            if(raw.type()!=CV_8UC1 || raw.size()!=calibration.size) throw std::runtime_error("Missing image or unexpected camera dimensions/type");
            cv::remap(raw,image,calibration.x,calibration.y,cv::INTER_LINEAR);
            auto prepared=Clock::now(); std::vector<cv::KeyPoint> keys; cv::Mat descriptors; std::vector<int> overlap={0,0};
            extractor(image,cv::Mat(),keys,descriptors,overlap);
            auto extracted=Clock::now(); std::vector<cv::Mat> rows;
            for(int r=0;r<descriptors.rows;++r) rows.push_back(descriptors.row(r));
            DBoW2::BowVector bow; DBoW2::FeatureVector features;
            vocabulary.transform(rows,bow,features,4);
            auto encoded=Clock::now(); std::vector<std::pair<double,long long>> scores; size_t eligible=0;
            for(const auto& entry:history) {
                if(stamp-entry.stamp<exclusion) continue;
                ++eligible; double score=vocabulary.score(bow,entry.bow);
                if(score>0) scores.emplace_back(score,entry.stamp);
            }
            std::sort(scores.begin(),scores.end(),[](const auto& a,const auto& b){return a.first!=b.first?a.first>b.first:a.second<b.second;});
            if(scores.size()>size_t(k)) scores.resize(k);
            auto retrieved=Clock::now();
            std::cout << "{\"query_timestamp_ns\":" << stamp << ",\"eligible_history_count\":" << eligible << ",\"feature_count\":" << descriptors.rows << ",\"bow_word_count\":" << bow.size()
                      << ",\"timings_ms\":{\"image_preparation\":" << ms(start,prepared) << ",\"feature_extraction\":" << ms(prepared,extracted) << ",\"bow_encoding\":" << ms(extracted,encoded) << ",\"retrieval\":" << ms(encoded,retrieved) << "},\"candidates\":[";
            for(size_t i=0;i<scores.size();++i) {if(i) std::cout << ','; std::cout << "{\"rank\":" << i+1 << ",\"historical_timestamp_ns\":" << scores[i].second << ",\"score\":" << scores[i].first << "}";}
            std::cout << "]}" << std::endl;
            if(argc==7) dump(std::string(argv[6])+"_"+std::to_string(stamp),image,descriptors,bow);
            if(featureDirectory) {
                const std::string prefix=std::string(featureDirectory)+"/"+std::to_string(stamp);
                dump_features(prefix+"_cam0.orb",image,keys,descriptors,calibration.x,calibration.y);
                std::string rightPath=line.substr(tab+1); auto camera=rightPath.find("/cam0/data/");
                if(camera==std::string::npos) throw std::runtime_error("Cannot locate synchronized cam1 image");
                rightPath.replace(camera,11,"/cam1/data/");
                cv::Mat rightRaw=cv::imread(rightPath,cv::IMREAD_UNCHANGED),rightImage;
                if(rightRaw.type()!=CV_8UC1 || rightRaw.size()!=calibration.size) throw std::runtime_error("Missing synchronized cam1 image");
                cv::remap(rightRaw,rightImage,calibration.xright,calibration.yright,cv::INTER_LINEAR);
                std::vector<cv::KeyPoint> rightKeys;cv::Mat rightDescriptors;
                rightExtractor(rightImage,cv::Mat(),rightKeys,rightDescriptors,overlap);
                dump_features(prefix+"_cam1.orb",rightImage,rightKeys,rightDescriptors,calibration.xright,calibration.yright);
                if(argc==7) dump(std::string(argv[6])+"_right_"+std::to_string(stamp),rightImage,rightDescriptors,{});
            }
            history.push_back({stamp,std::move(bow)}); // Insert only after query.
        }
        if(history.empty()) throw std::runtime_error("Empty replay");
        return 0;
    } catch(const std::exception& e) {std::cerr << e.what() << std::endl; return 1;}
}
