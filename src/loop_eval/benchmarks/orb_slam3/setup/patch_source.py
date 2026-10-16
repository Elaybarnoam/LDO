"""Apply checked instrumentation separately from compiler/lifecycle compatibility edits."""

import difflib
import shutil
from pathlib import Path


def apply(root: Path, instrumentation: Path):
    patches = {"instrumentation": [], "compatibility": []}

    def edit(name, old, new, category="instrumentation", occurrences=1, scope=None):
        path = root / name
        before = path.read_text()
        start = before.index(scope) if scope else 0
        end = before.index("\n}\n", start) + 3 if scope else len(before)
        section = before[start:end]
        if section.count(old) != occurrences:
            raise ValueError(f"Pinned-source patch mismatch: {name}: {old[:70]!r}")
        after = before[:start] + section.replace(old, new) + before[end:]
        path.write_text(after)
        patches[category].extend(
            difflib.unified_diff(
                before.splitlines(True),
                after.splitlines(True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )

    edit("CMakeLists.txt", "src/System.cc", "src/EvaluationEvents.cc\nsrc/System.cc")
    edit("CMakeLists.txt", "-std=c++11", "-std=c++14", "compatibility", 3)
    edit(
        "src/KeyFrame.cc",
        '#include "KeyFrame.h"',
        '#include "KeyFrame.h"\n#include "EvaluationEvents.h"',
    )
    edit(
        "src/KeyFrame.cc",
        "mnOriginMapId = pMap->GetId();",
        "mnOriginMapId = pMap->GetId();\n    EvaluationEvents::keyframe(this);",
    )
    edit(
        "src/LoopClosing.cc",
        '#include "LoopClosing.h"',
        '#include "LoopClosing.h"\n#include "EvaluationEvents.h"',
    )
    edit(
        "src/KeyFrameDatabase.cc",
        '#include "KeyFrameDatabase.h"',
        '#include "KeyFrameDatabase.h"\n#include "EvaluationEvents.h"',
    )

    def db(old, new):
        edit(
            "src/KeyFrameDatabase.cc",
            old,
            new,
            scope="void KeyFrameDatabase::DetectNBestCandidates(",
        )

    db(
        "    list<KeyFrame*> lKFsSharingWords;",
        "    list<KeyFrame*> lKFsSharingWords;\n    set<KeyFrame*> evaluationWordPool;",
    )
    db(
        "                KeyFrame* pKFi=*lit;",
        "                KeyFrame* pKFi=*lit;\n                evaluationWordPool.insert(pKFi);",
    )
    db(
        "    if(lKFsSharingWords.empty())",
        "    for(KeyFrame* candidate : evaluationWordPool)\n"
        '        EvaluationEvents::candidate(pKF, candidate, "database_word_pool", spConnectedKF.count(candidate) ? "direct_connected" : "eligible");\n'
        "    if(lKFsSharingWords.empty())",
    )
    db(
        "        if(pKFi->mnPlaceRecognitionWords>minCommonWords)",
        '        EvaluationEvents::candidate(pKF, pKFi, "shared_words", pKFi->mnPlaceRecognitionWords>minCommonWords ? "passed" : "insufficient_shared_words", pKFi->mnPlaceRecognitionWords, minCommonWords + 1);\n'
        "        if(pKFi->mnPlaceRecognitionWords>minCommonWords)",
    )
    db(
        "        it++;\n    }\n}",
        "        it++;\n    }\n"
        "    set<KeyFrame*> evaluationSelected(vpLoopCand.begin(), vpLoopCand.end());\n"
        "    evaluationSelected.insert(vpMergeCand.begin(), vpMergeCand.end());\n"
        "    for(KeyFrame* candidate : evaluationSelected)\n"
        '        EvaluationEvents::candidate(pKF, candidate, "top_k", "selected");\n'
        "    for(KeyFrame* candidate : lKFsSharingWords)\n"
        "        if(candidate->mnPlaceRecognitionWords>minCommonWords && !evaluationSelected.count(candidate))\n"
        '            EvaluationEvents::candidate(pKF, candidate, "top_k", "not_selected_top_k");\n'
        "}",
    )
    edit(
        "src/LoopClosing.cc",
        "        mpKeyFrameDB->DetectNBestCandidates(mpCurrentKF, vpLoopBowCand, vpMergeBowCand,3);",
        "        mpKeyFrameDB->DetectNBestCandidates(mpCurrentKF, vpLoopBowCand, vpMergeBowCand,3);\n        EvaluationEvents::retrieval(mpCurrentKF, vpLoopBowCand.size(), vpMergeBowCand.size());",
    )
    edit(
        "src/LoopClosing.cc",
        "        if(!pKFi || pKFi->isBad())\n            continue;",
        '        if(!pKFi || pKFi->isBad()) {\n            if(pKFi) EvaluationEvents::candidate(mpCurrentKF, pKFi, "geometry_filter", "bad_keyframe");\n            continue;\n        }',
        scope="bool LoopClosing::DetectCommonRegionsFromBoW(",
    )
    edit(
        "src/LoopClosing.cc",
        "        if(bAbortByNearKF)\n        {",
        '        if(bAbortByNearKF)\n        {\n            EvaluationEvents::candidate(mpCurrentKF, pKFi, "geometry_filter", "connected_neighbourhood");',
    )
    edit(
        "include/Sim3Solver.h",
        "    float GetEstimatedScale();",
        "    float GetEstimatedScale();\n    int EvaluationUsable() const { return N; }\n    int EvaluationBestInliers() const { return mnBestInliers; }\n    int EvaluationIterations() const { return mnIterations; }\n    int EvaluationIterationLimit() const { return mRansacMaxIts; }",
    )
    edit(
        "src/LoopClosing.cc",
        "bool bFindedRegion = NewDetectCommonRegions();",
        'bool bFindedRegion;\n            { EvaluationEvents::Timer timer("place_recognition"); bFindedRegion = NewDetectCommonRegions(); }',
    )
    edit(
        "src/LoopClosing.cc",
        "    if(mpLastMap->IsInertial() && !mpLastMap->GetIniertialBA2())\n    {",
        '    if(mpLastMap->IsInertial() && !mpLastMap->GetIniertialBA2())\n    {\n        EvaluationEvents::query(mpCurrentKF, false, "imu_ba2_not_ready");',
    )
    edit(
        "src/LoopClosing.cc",
        '        // cout << "LoopClousure: Stereo KF inserted without check: "',
        '        EvaluationEvents::query(mpCurrentKF, false, "small_stereo_map");\n        // cout << "LoopClousure: Stereo KF inserted without check: "',
    )
    edit(
        "src/LoopClosing.cc",
        '        // cout << "LoopClousure: Stereo KF inserted without check, map is small: "',
        '        EvaluationEvents::query(mpCurrentKF, false, "small_map");\n        // cout << "LoopClousure: Stereo KF inserted without check, map is small: "',
    )
    edit(
        "src/LoopClosing.cc",
        '    //cout << "LoopClousure: Checking KF: "',
        '    EvaluationEvents::query(mpCurrentKF, true, "eligible");\n    //cout << "LoopClousure: Checking KF: "',
    )
    edit(
        "src/LoopClosing.cc",
        "                    if (bGoodLoop) {",
        '                    EvaluationEvents::emit("loop_decision", EvaluationEvents::pairPayload(mpCurrentKF, mpLoopMatchedKF) + ",\\"accepted\\":" + (bGoodLoop ? "true" : "false") + ",\\"stage\\":\\"native_final_gate\\"", mpCurrentKF->mTimeStamp);\n                    if (bGoodLoop) {',
    )
    edit(
        "src/LoopClosing.cc",
        "        std::vector<std::vector<MapPoint*> > vvpMatchedMPs;",
        '        EvaluationEvents::candidate(mpCurrentKF, pKFi, "geometry_filter", "passed");\n        EvaluationEvents::Attempt evaluationAttempt(mpCurrentKF, pKFi, "bow_geometry");\n        std::vector<std::vector<MapPoint*> > vvpMatchedMPs;',
    )
    # Record the actual operands of each native gate; do not change any branch.
    edit(
        "src/LoopClosing.cc",
        "        if(numBoWMatches >= nBoWMatches)",
        '        evaluationAttempt.gate("bow_matches", numBoWMatches, nBoWMatches);\n        if(numBoWMatches >= nBoWMatches)',
    )
    edit(
        "src/LoopClosing.cc",
        "            if(bConverge)",
        '            evaluationAttempt.gate("sim3_ransac_convergence", bConverge ? 1 : 0, 1);\n'
        '            evaluationAttempt.observe("ransac_usable_correspondences", solver.EvaluationUsable());\n'
        '            evaluationAttempt.observe("ransac_best_inliers", solver.EvaluationBestInliers());\n'
        '            evaluationAttempt.observe("ransac_iterations", solver.EvaluationIterations());\n'
        '            evaluationAttempt.observe("ransac_iteration_limit", solver.EvaluationIterationLimit());\n'
        '            evaluationAttempt.observe("ransac_required_inliers", nBoWInliers + 1);\n'
        '            if(!bConverge) evaluationAttempt.reject(solver.EvaluationUsable() < nBoWInliers ? "insufficient_3d_correspondences" : "ransac_no_consensus");\n'
        "            if(bConverge)",
    )
    edit(
        "src/LoopClosing.cc",
        "                if(numProjMatches >= nProjMatches)",
        '                evaluationAttempt.gate("initial_projection_matches", numProjMatches, nProjMatches);\n                if(numProjMatches >= nProjMatches)',
    )
    edit(
        "src/LoopClosing.cc",
        "                    if(numOptMatches >= nSim3Inliers)",
        '                    evaluationAttempt.gate("optimized_sim3_inliers", numOptMatches, nSim3Inliers);\n                    if(numOptMatches >= nSim3Inliers)',
    )
    edit(
        "src/LoopClosing.cc",
        "                        if(numProjOptMatches >= nProjOptMatches)\n                        {",
        '                        evaluationAttempt.matches = numProjOptMatches;\n                        evaluationAttempt.gate("optimized_projection_matches", numProjOptMatches, nProjOptMatches);\n                        if(numProjOptMatches >= nProjOptMatches)\n                        {\n                            evaluationAttempt.accepted = true;',
    )
    edit(
        "src/LoopClosing.cc",
        "    set<MapPoint*> spAlreadyMatchedMPs;\n    nNumProjMatches = FindMatchesByProjection",
        '    EvaluationEvents::Attempt evaluationAttempt(pCurrentKF, pMatchedKF, "temporal_refinement");\n    set<MapPoint*> spAlreadyMatchedMPs;\n    nNumProjMatches = FindMatchesByProjection',
    )
    edit(
        "src/LoopClosing.cc",
        "                gScw = gScw_estimation;\n                return true;",
        "                gScw = gScw_estimation;\n                evaluationAttempt.accepted = true;\n                evaluationAttempt.matches = nNumProjMatches;\n                return true;",
    )
    edit(
        "src/LoopClosing.cc",
        "    int nProjMatchesRep = 100;\n\n    if(nNumProjMatches >= nProjMatches)",
        '    int nProjMatchesRep = 100;\n\n    evaluationAttempt.gate("refinement_initial_projection", nNumProjMatches, nProjMatches);\n    if(nNumProjMatches >= nProjMatches)',
    )
    edit(
        "src/LoopClosing.cc",
        "        if(numOptMatches > nProjOptMatches)",
        '        evaluationAttempt.gate("refinement_optimized_inliers", numOptMatches, nProjOptMatches + 1);\n        if(numOptMatches > nProjOptMatches)',
    )
    edit(
        "src/LoopClosing.cc",
        "            if(nNumProjMatches >= nProjMatchesRep)",
        '            evaluationAttempt.gate("refinement_reprojection", nNumProjMatches, nProjMatchesRep);\n            if(nNumProjMatches >= nProjMatchesRep)',
    )
    edit(
        "src/LoopClosing.cc",
        "    mpCurrentKF->AddLoopEdge(mpLoopMatchedKF);",
        '    mpCurrentKF->AddLoopEdge(mpLoopMatchedKF);\n    EvaluationEvents::pairEvent("constraint_inserted", mpCurrentKF, mpLoopMatchedKF);',
    )
    # Capture maps before native merging moves keyframes between maps.
    edit(
        "src/LoopClosing.cc",
        "                        // TODO UNCOMMENT",
        "                        const std::string evaluationMerge = EvaluationEvents::pairPayload(mpCurrentKF, mpMergeMatchedKF);\n                        // TODO UNCOMMENT",
    )
    edit(
        "src/LoopClosing.cc",
        '                        Verbose::PrintMess("Merge finished!", Verbose::VERBOSITY_QUIET);',
        '                        EvaluationEvents::emit("map_merge", evaluationMerge, mpCurrentKF->mTimeStamp);\n                        Verbose::PrintMess("Merge finished!", Verbose::VERBOSITY_QUIET);',
    )
    example = "Examples/Stereo-Inertial/stereo_inertial_euroc.cc"
    edit(example, '#include "Optimizer.h"', '#include "Optimizer.h"\n#include "EvaluationEvents.h"')
    edit(
        example,
        "    // Load all sequences:",
        "    ORB_SLAM3::EvaluationEvents::initialize();\n    // Load all sequences:",
    )
    edit(
        example,
        "            vTimesTrack[ni]=ttrack;",
        '            vTimesTrack[ni]=ttrack;\n            ORB_SLAM3::EvaluationEvents::emit("timing", "\\"operation\\":\\"tracking\\",\\"seconds\\":" + std::to_string(ttrack), tframe);',
    )
    edit(
        example,
        "    return 0;",
        '    ORB_SLAM3::EvaluationEvents::emit("native_finished", "");\n    return 0;',
    )
    # The upstream Shutdown has its thread wait commented out. Join mapping first,
    # then request loop finish, draining both queues before saving trajectories.
    edit(
        "src/LocalMapping.cc",
        "        if(CheckFinish())\n            break;",
        "        if(CheckFinish() && !CheckNewKeyFrames())\n            break;",
        "compatibility",
    )
    edit(
        "src/LoopClosing.cc",
        "        if(CheckFinish()){",
        "        if(CheckFinish() && !CheckNewKeyFrames()){",
        "compatibility",
    )
    edit(
        "src/System.cc",
        "    mpLocalMapper->RequestFinish();\n    mpLoopCloser->RequestFinish();",
        "    mpLocalMapper->RequestFinish();\n    mptLocalMapping->join();\n    mpLoopCloser->RequestFinish();\n    mptLoopClosing->join();\n    while(mpLoopCloser->isRunningGBA()) usleep(5000);",
        "compatibility",
    )
    for name in ("EvaluationEvents.h", "EvaluationEvents.cc"):
        shutil.copyfile(
            instrumentation / name, root / ("include" if name.endswith(".h") else "src") / name
        )
    for category, lines in patches.items():
        (root / f"evaluation-{category}.patch").write_text("".join(lines))
