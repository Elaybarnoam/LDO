// Reuses GPL-3.0-or-later ORB-SLAM3/DBoW2 components. See README.md.
#pragma once
#include "ORBextractor.h"
#include "ORBVocabulary.h"
#include <opencv2/opencv.hpp>
#include <fstream>
#include <iomanip>
#include <cstdint>

// Export the exact descriptors used by retrieval, with coordinates mapped
// back through the rectification maps into the original sensor image.
inline void dump_features(const std::string& path, const cv::Mat& image,
                          const std::vector<cv::KeyPoint>& keys, const cv::Mat& descriptors,
                          const cv::Mat& mapx, const cv::Mat& mapy) {
    if(keys.size()!=size_t(descriptors.rows) || (descriptors.rows && (descriptors.cols!=32 || descriptors.type()!=CV_8UC1)))
        throw std::runtime_error("Invalid native ORB descriptor shape");
    std::ofstream file(path, std::ios::binary);
    if(!file) throw std::runtime_error("Cannot write ORB feature export");
    file.write("LDORB001",8);
    uint32_t header[3]={uint32_t(keys.size()),uint32_t(image.cols),uint32_t(image.rows)};
    file.write(reinterpret_cast<char*>(header),sizeof(header));
    for(size_t i=0;i<keys.size();++i) {
        cv::Mat rawx,rawy;
        cv::getRectSubPix(mapx,cv::Size(1,1),keys[i].pt,rawx);
        cv::getRectSubPix(mapy,cv::Size(1,1),keys[i].pt,rawy);
        float values[5]={keys[i].pt.x,keys[i].pt.y,rawx.at<float>(0,0),rawy.at<float>(0,0),keys[i].angle};
        int32_t octave=keys[i].octave;
        file.write(reinterpret_cast<char*>(values),sizeof(values));
        file.write(reinterpret_cast<char*>(&octave),sizeof(octave));
        file.write(reinterpret_cast<const char*>(descriptors.ptr(int(i))),32);
    }
    if(!file) throw std::runtime_error("Truncated ORB feature export");
}

inline void dump(const std::string& prefix, const cv::Mat& image,
                 const cv::Mat& descriptors, const DBoW2::BowVector& bow) {
    cv::imwrite(prefix + ".png", image);
    std::ofstream bytes(prefix + ".descriptors", std::ios::binary);
    for(int r=0; r<descriptors.rows; ++r)
        bytes.write(reinterpret_cast<const char*>(descriptors.ptr(r)), descriptors.cols);
    std::ofstream words(prefix + ".bow");
    words << std::setprecision(17);
    for(const auto& word: bow) words << word.first << " " << word.second << "\n";
}
