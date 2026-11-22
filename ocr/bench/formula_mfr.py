# SPDX-License-Identifier: LicenseRef-HST-Proprietary
"""Comparison candidate: Pix2Text MFR 1.5 (TrOCR, MIT weights) on ONNX Runtime with greedy decoding.

Only the recogniser is used, never the Pix2Text pipeline or its YOLO formula detector (Ultralytics, AGPL).
"""
import os

import numpy as np
from PIL import Image

BOS, EOS, MAX_TOKENS = 1, 2, 256


class Mfr:
    def __init__(self, model_dir, threads=2):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self.encoder = ort.InferenceSession(os.path.join(model_dir, "encoder_model.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.decoder = ort.InferenceSession(os.path.join(model_dir, "decoder_model.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))

    def __call__(self, image):
        rgb = image.convert("RGB").resize((384, 384), Image.BICUBIC)
        pixels = (np.asarray(rgb, dtype=np.float32) / 255.0 - 0.5) / 0.5
        hidden = self.encoder.run(None, {"pixel_values": pixels.transpose(2, 0, 1)[None]})[0]
        ids = [BOS]
        for _ in range(MAX_TOKENS):  # no KV cache in this export: O(n^2), fine for formula-length outputs
            logits = self.decoder.run(None, {"input_ids": np.array([ids], dtype=np.int64),
                                             "encoder_hidden_states": hidden})[0]
            nxt = int(np.argmax(logits[0, -1]))
            if nxt == EOS:
                break
            ids.append(nxt)
        return self.tokenizer.decode(ids[1:], skip_special_tokens=True).strip()
