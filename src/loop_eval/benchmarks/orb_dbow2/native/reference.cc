// Verification oracle using actual upstream Settings, Frame::ExtractORB,
// Frame::ComputeBoW. Never used by the benchmark runner.
#include "common.h"
#include "System.h"
#include "Frame.h"
#include "Settings.h"
#include <iostream>

int main(int argc,char** argv) {
    if(argc!=5) return 2;
    cv::setNumThreads(1);
    ORB_SLAM3::Settings settings(argv[2],ORB_SLAM3::System::IMU_STEREO);
    ORB_SLAM3::ORBVocabulary vocabulary;
    if(!vocabulary.loadFromTextFile(argv[1])) return 3;
    ORB_SLAM3::ORBextractor extractor(settings.nFeatures(),settings.scaleFactor(),settings.nLevels(),settings.initThFAST(),settings.minThFAST());
    std::ifstream replay(argv[3]); std::string line;
    DBoW2::BowVector previous;
    while(std::getline(replay,line)) {
        auto tab=line.find('\t'); cv::Mat raw=cv::imread(line.substr(tab+1),cv::IMREAD_UNCHANGED),image;
        if(raw.empty()) return 4;
        cv::remap(raw,image,settings.M1l(),settings.M2l(),cv::INTER_LINEAR);
        ORB_SLAM3::Frame frame;
        frame.mpORBextractorLeft=&extractor;
        frame.mpORBvocabulary=&vocabulary;
        frame.ExtractORB(0,image,0,0);
        frame.ComputeBoW();
        dump_features(std::string(argv[4])+"_"+line.substr(0,tab)+"_cam0.orb",image,frame.mvKeys,frame.mDescriptors,settings.M1l(),settings.M2l());
        auto rightPath=line.substr(tab+1); auto camera=rightPath.find("/cam0/data/");
        rightPath.replace(camera,11,"/cam1/data/");
        cv::Mat rightRaw=cv::imread(rightPath,cv::IMREAD_UNCHANGED),rightImage;
        cv::remap(rightRaw,rightImage,settings.M1r(),settings.M2r(),cv::INTER_LINEAR);
        ORB_SLAM3::Frame rightFrame; rightFrame.mpORBextractorRight=&extractor;
        rightFrame.ExtractORB(1,rightImage,0,0);
        dump_features(std::string(argv[4])+"_"+line.substr(0,tab)+"_cam1.orb",rightImage,rightFrame.mvKeysRight,rightFrame.mDescriptorsRight,settings.M1r(),settings.M2r());
        if(!previous.empty()) std::cout << "REFERENCE_SCORE " << std::setprecision(17) << vocabulary.score(previous,frame.mBowVec) << std::endl;
        previous=frame.mBowVec;
        dump(std::string(argv[4])+"_"+line.substr(0,tab),image,frame.mDescriptors,frame.mBowVec);
    }
    return 0;
}
