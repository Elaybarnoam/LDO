// Evaluation hooks added to official ORB-SLAM3; see upstream GPLv3 license.
#include "EvaluationEvents.h"
#include "KeyFrame.h"
#include "Map.h"
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <map>
#include <mutex>
#include <sstream>
#include <stdexcept>

namespace ORB_SLAM3 { namespace EvaluationEvents {
namespace {
std::mutex mutex;
std::ofstream trace;
std::map<double, long long> timestamps;
unsigned long long number = 0, attempt = 0;

long long stamp(double timestamp) {
    auto found = timestamps.find(timestamp);
    if (found == timestamps.end()) throw std::runtime_error("Missing source timestamp association");
    return found->second;
}
void write(const std::string& type, const std::string& payload, double timestamp) {
    if (!trace.is_open()) return;
    trace << "{\"schema_version\":1,\"event_number\":" << ++number
          << ",\"event_type\":\"" << type << "\",\"dataset_timestamp_ns\":";
    if (timestamp < 0) trace << "null"; else trace << stamp(timestamp);
    trace << ",\"payload\":{" << payload << "}}\n";
    trace.flush();
    if (!trace) throw std::runtime_error("Evaluation trace write failed");
}
}

void initialize() {
    std::lock_guard<std::mutex> lock(mutex);
    const char* output = std::getenv("ORB_EVALUATION_TRACE");
    if (!output) return;
    const char* input = std::getenv("ORB_EVALUATION_TIMESTAMPS");
    if (!input) throw std::runtime_error("Missing source timestamp file");
    std::ifstream stream(input);
    if (!stream) throw std::runtime_error("Cannot open timestamp file");
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty()) timestamps.emplace(std::stod(line) / 1e9, std::stoll(line));
    }
    trace.open(output, std::ios::out | std::ios::trunc);
    if (!trace) throw std::runtime_error("Cannot create native trace");
    write("instrumentation_ready", "\"revision\":\"4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4\",\"instrumentation_version\":6,\"sensor\":\"stereo_imu\"", -1);
}
void emit(const std::string& type, const std::string& payload, double timestamp) {
    std::lock_guard<std::mutex> lock(mutex);
    write(type, payload, timestamp);
}
std::string pairPayload(KeyFrame* query, KeyFrame* historical) {
    return "\"query_keyframe_id\":" + std::to_string(query->mnId) +
           ",\"historical_keyframe_id\":" + std::to_string(historical->mnId) +
           ",\"query_map_id\":" + std::to_string(query->GetMap()->GetId()) +
           ",\"historical_map_id\":" + std::to_string(historical->GetMap()->GetId()) +
           ",\"query_frame_id\":" + std::to_string(query->mnFrameId) +
           ",\"historical_frame_id\":" + std::to_string(historical->mnFrameId) +
           ",\"query_timestamp_ns\":" + (timestamps.empty() ? "null" : std::to_string(stamp(query->mTimeStamp))) +
           ",\"historical_timestamp_ns\":" + (timestamps.empty() ? "null" : std::to_string(stamp(historical->mTimeStamp)));
}
void pairEvent(const std::string& type, KeyFrame* query, KeyFrame* historical) {
    emit(type, pairPayload(query, historical), query->mTimeStamp);
}
void keyframe(KeyFrame* frame) {
    emit("keyframe_created", "\"keyframe_id\":" + std::to_string(frame->mnId) +
         ",\"frame_id\":" + std::to_string(frame->mnFrameId) +
         ",\"map_id\":" + std::to_string(frame->GetMap()->GetId()), frame->mTimeStamp);
}
void query(KeyFrame* frame, bool eligible, const std::string& reason) {
    emit("loop_query", "\"keyframe_id\":" + std::to_string(frame->mnId) +
         ",\"frame_id\":" + std::to_string(frame->mnFrameId) +
         ",\"map_id\":" + std::to_string(frame->GetMap()->GetId()) +
         ",\"eligible\":" + (eligible ? "true" : "false") +
         ",\"eligibility_reason\":\"" + reason + "\"", frame->mTimeStamp);
}
void candidate(KeyFrame* query, KeyFrame* historical, const std::string& stage,
               const std::string& reason, int words, int required) {
    emit("loop_candidate", pairPayload(query, historical) +
         ",\"selection_stage\":\"" + stage + "\",\"selection_reason\":\"" + reason + "\"" +
         ",\"candidate_kind\":\"" + (query->GetMap() == historical->GetMap() ? "loop" : "map_merge") + "\"" +
         ",\"shared_words\":" + (words < 0 ? "null" : std::to_string(words)) +
         ",\"required_words\":" + (required < 0 ? "null" : std::to_string(required)), query->mTimeStamp);
}
void retrieval(KeyFrame* frame, int loops, int merges) {
    emit("loop_retrieval", "\"keyframe_id\":" + std::to_string(frame->mnId) +
         ",\"frame_id\":" + std::to_string(frame->mnFrameId) +
         ",\"map_id\":" + std::to_string(frame->GetMap()->GetId()) +
         ",\"loop_candidates\":" + std::to_string(loops) +
         ",\"merge_candidates\":" + std::to_string(merges) +
         ",\"limit_per_kind\":3", frame->mTimeStamp);
}
Attempt::Attempt(KeyFrame* query, KeyFrame* historical, const std::string& stage)
    : family_(query->GetMap() == historical->GetMap() ? "loop" : "map_merge"),
      payload_(pairPayload(query, historical)), timestamp_(query->mTimeStamp), started_(std::chrono::steady_clock::now()) {
    std::lock_guard<std::mutex> lock(mutex);
    payload_ += ",\"attempt_id\":" + std::to_string(++attempt) + ",\"stage\":\"" + stage + "\"";
    write(family_ + "_proposed", payload_, timestamp_);
}
void Attempt::gate(const std::string& name, int observed, int threshold) {
    if (!measurements_.empty()) measurements_ += ",";
    const bool passed = observed >= threshold;
    measurements_ += "\"" + name + "\":{\"observed\":" + std::to_string(observed) +
                     ",\"threshold\":" + std::to_string(threshold) +
                     ",\"passed\":" + (passed ? "true" : "false") + "}";
    rejection_reason_ = passed ? "unreported" : name;
}
void Attempt::observe(const std::string& name, int value) {
    if (!diagnostics_.empty()) diagnostics_ += ",";
    diagnostics_ += "\"" + name + "\":" + std::to_string(value);
}
void Attempt::reject(const std::string& reason) { rejection_reason_ = reason; }
Attempt::~Attempt() {
    const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started_).count();
    std::ostringstream duration;
    duration << std::setprecision(17) << seconds;
    emit(family_ + "_verified", payload_ + ",\"accepted\":" + (accepted ? "true" : "false") +
         ",\"projection_matches\":" + (matches < 0 ? "null" : std::to_string(matches)) +
         ",\"rejection_reason\":" + (accepted ? "null" : "\"" + rejection_reason_ + "\"") +
         ",\"gate_measurements\":{" + measurements_ + "}" +
         ",\"diagnostics\":{" + diagnostics_ + "}" +
         ",\"verification_seconds\":" + duration.str(), timestamp_);
}
Timer::Timer(const std::string& operation) : operation_(operation), started_(std::chrono::steady_clock::now()) {}
Timer::~Timer() {
    const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started_).count();
    std::ostringstream payload;
    payload << std::setprecision(17) << "\"operation\":\"" << operation_ << "\",\"seconds\":" << seconds;
    emit("timing", payload.str());
}
}}
