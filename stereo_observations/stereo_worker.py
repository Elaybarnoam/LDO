"""Persistent inference using NVIDIA's pinned official ONNX stereo export."""
from contextlib import redirect_stdout
import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    import onnxruntime as ort
    torch.set_num_threads(2)
    cv2.setNumThreads(1)
    if not torch.cuda.is_available():
        raise RuntimeError("Fast-FoundationStereo requires the configured CUDA GPU runtime")
    with redirect_stdout(sys.stderr):
        ort.preload_dlls()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(args.checkpoint, sess_options=options,
                                       providers=[("CUDAExecutionProvider", {"gpu_mem_limit": 6*1024**3}), "CPUExecutionProvider"])
    if "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("Stereo ONNX CUDA provider failed to initialize")
    inputs = session.get_inputs()
    if len(inputs) != 2:
        raise ValueError("Unexpected official stereo graph input schema")
    mean = np.array([.485, .456, .406], np.float32)
    std = np.array([.229, .224, .225], np.float32)

    def predict(left, right):
        height, width = left.shape[:2]
        ph, pw = (-height)%32, (-width)%32
        arrays = []
        for image in (left, right):
            image = (image.astype(np.float32)/255 - mean)/std
            image = np.pad(image, ((0, ph), (0, pw), (0, 0)), mode="edge")
            arrays.append(np.ascontiguousarray(image.transpose(2, 0, 1)[None]))
        result = session.run(None, {i.name: a.astype(np.float16 if i.type == "tensor(float16)" else np.float32)
                                    for i, a in zip(inputs, arrays)})[0]
        return np.asarray(result, np.float32).reshape(height+ph, width+pw)[:height, :width]

    print(json.dumps({"ready": True, "onnxruntime": ort.__version__, "torch": torch.__version__,
                      "providers": session.get_providers(), "device": torch.cuda.get_device_name(0),
                      "model_format": "official_onnx", "baked_inference_settings": True}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        left, right = [cv2.imread(request[k], cv2.IMREAD_COLOR) for k in ("left", "right")]
        if left is None or right is None or left.shape != right.shape:
            raise ValueError("Inference images missing or inconsistent")
        left, right = left[:, :, ::-1], right[:, :, ::-1]
        dl = predict(left, right)
        dr = predict(right[:, ::-1], left[:, ::-1])[:, ::-1]
        np.savez_compressed(request["output"], left=dl, right=dr)
        print(json.dumps({"output": request["output"]}), flush=True)


if __name__ == "__main__":
    main()
