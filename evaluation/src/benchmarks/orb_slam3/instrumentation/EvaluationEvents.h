// Evaluation hooks added to official ORB-SLAM3; see upstream GPLv3 license.
#pragma once
#include <chrono>
#include <string>

namespace ORB_SLAM3 {
class KeyFrame;
namespace EvaluationEvents {
void initialize();
void emit(const std::string& type, const std::string& payload, double timestamp = -1);
std::string pairPayload(KeyFrame* query, KeyFrame* historical);
void pairEvent(const std::string& type, KeyFrame* query, KeyFrame* historical);
void keyframe(KeyFrame* frame);
void query(KeyFrame* frame, bool eligible, const std::string& reason);
void candidate(KeyFrame* query, KeyFrame* historical, const std::string& stage,
               const std::string& reason, int words = -1, int required = -1);
void retrieval(KeyFrame* frame, int loops, int merges);

class Attempt {
public:
    Attempt(KeyFrame* query, KeyFrame* historical, const std::string& stage);
    ~Attempt();
    void gate(const std::string& name, int observed, int threshold);
    void observe(const std::string& name, int value);
    void reject(const std::string& reason);
    bool accepted = false;
    int matches = -1;
private:
    std::string family_, payload_;
    std::string rejection_reason_ = "unreported", measurements_;
    std::string diagnostics_;
    double timestamp_;
    std::chrono::steady_clock::time_point started_;
};

class Timer {
public:
    explicit Timer(const std::string& operation);
    ~Timer();
private:
    std::string operation_;
    std::chrono::steady_clock::time_point started_;
};
}
}
