# Copyright 2025 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pytest
import json
import tempfile
import unittest
import shutil
from parameterized import parameterized

import torch
from transformers import AutoTokenizer, GPT2TokenizerFast

from transformers.testing_utils import (
    require_torch,
    require_torchaudio,
    require_torch_gpu,
)
from transformers.utils import is_torchaudio_available


if is_torchaudio_available():
    from transformers import GraniteSpeechProcessor, GraniteSpeechFeatureExtractor

pytest.skip("Public models not yet available", allow_module_level=True)
@require_torch
@require_torchaudio
class GraniteSpeechProcessorTest(unittest.TestCase):
    def setUp(self):
        self.tmpdirname = tempfile.mkdtemp()
        # TODO - use the actual model path on HF hub after release.
        self.checkpoint = "ibm-granite/granite-speech"
        processor = GraniteSpeechProcessor.from_pretrained(self.checkpoint)
        processor.save_pretrained(self.tmpdirname)

    def get_tokenizer(self, **kwargs):
        return AutoTokenizer.from_pretrained(self.checkpoint, **kwargs)

    def get_feature_extractor(self, **kwargs):
        return GraniteSpeechFeatureExtractor.from_pretrained(self.checkpoint, **kwargs)

    def tearDown(self):
        shutil.rmtree(self.tmpdirname)

    def test_save_load_pretrained_default(self):
        """Ensure we can save / reload a processor correctly."""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        processor.save_pretrained(self.tmpdirname)
        processor = GraniteSpeechProcessor.from_pretrained(self.tmpdirname)

        self.assertEqual(processor.tokenizer.get_vocab(), tokenizer.get_vocab())
        self.assertIsInstance(processor.tokenizer, GPT2TokenizerFast)

        self.assertEqual(processor.feature_extractor.to_json_string(), feature_extractor.to_json_string())
        self.assertIsInstance(processor.feature_extractor, GraniteSpeechFeatureExtractor)

    def test_requires_text(self):
        """Ensure we require text"""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        with pytest.raises(TypeError):
            processor(text=None)

    def test_bad_text_fails(self):
        """Ensure we gracefully fail if text is the wrong type."""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()

        processor = GraniteSpeechProcessor(tokenizer=tokenizer, feature_extractor=feature_extractor)
        with pytest.raises(TypeError):
            processor(text=424, audios=None)

    def test_bad_nested_text_fails(self):
        """Ensure we gracefully fail if text is the wrong nested type."""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        with pytest.raises(TypeError):
            processor(text=[424], audios=None)

    def test_bad_audios_fails(self):
        """Ensure we gracefully fail if audio is the wrong type."""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        with pytest.raises(TypeError):
            processor(text=None, audios="foo")

    def test_bad_audios_fails(self):
        """Ensure we gracefully fail if audio is the wrong nested type."""
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        with pytest.raises(TypeError):
            processor(text=None, audios=["foo"])

    @parameterized.expand([
        ([1, 269920], [171]),
        ([2, 269920], [171, 171]),
    ])
    def test_audio_token_filling_same_len_feature_tensors(self, vec_dims, num_expected_features):
        """Ensure audio token filling is handled correctly when we have
        one or more audio inputs whose features are all the same length
        stacked into a tensor.
        """
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )
        audios = torch.rand(vec_dims) - .5

        audio_tokens = processor.audio_token * vec_dims[0]
        inputs = processor(
            text=f"{audio_tokens} Can you compare this audio?",
            audios=audios,
            return_tensors="pt"
        )

        # Check the number of audio tokens
        audio_token_id = tokenizer.get_vocab()[processor.audio_token]

        # Make sure the number of audio tokens matches the number of features
        num_computed_features = processor.feature_extractor._get_num_audio_features(
            [vec_dims[1] for _ in range(vec_dims[0])],
        )
        num_audio_tokens = int(torch.sum(inputs["input_ids"] == audio_token_id))
        assert sum(num_computed_features) == num_audio_tokens
        assert num_expected_features == num_expected_features

    def test_audio_token_filling_varying_len_feature_list(self):
        """Ensure audio token filling is handled correctly when we have
        multiple varying len audio sequences passed as a list.
        """
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )
        vec_dims = [[1, 142100], [1, 269920]]
        num_expected_features = [90, 171]
        audios = [torch.rand(dims) - .5 for dims in vec_dims]

        audio_tokens = processor.audio_token * len(vec_dims)
        inputs = processor(
            text=f"{audio_tokens} Can you compare this audio?",
            audios=audios,
            return_tensors="pt"
        )

        # Check the number of audio tokens
        audio_token_id = tokenizer.get_vocab()[processor.audio_token]

        # Make sure the number of audio tokens matches the number of features
        num_calculated_features = processor.feature_extractor._get_num_audio_features(
            [dims[1] for dims in vec_dims],
        )
        num_audio_tokens = int(torch.sum(inputs["input_ids"] == audio_token_id))
        assert num_calculated_features == [90, 171]
        assert sum(num_expected_features) == num_audio_tokens

    @require_torch_gpu
    def test_device_override(self):
        """Ensure that we regardless of the processing device, the tensors
        produced are on the CPU.
        """
        tokenizer = self.get_tokenizer()
        feature_extractor = self.get_feature_extractor()
        processor = GraniteSpeechProcessor(
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
        )

        vec_dims = [1, 269920]
        wav = torch.rand(vec_dims) - .5

        inputs = processor(
            text=f"{processor.audio_token} Can you transcribe this audio?",
            audios=wav,
            return_tensors="pt",
            device="cuda",
        )

        assert inputs["input_features"].device.type == "cpu"
