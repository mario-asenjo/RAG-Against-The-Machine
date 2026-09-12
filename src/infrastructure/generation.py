"""Lazy CPU Transformers adapter for Qwen/Qwen3-0.6B."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tqdm import tqdm

MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"
_SENTINEL_CONTEXT = 10**20
_SYSTEM_INSTRUCTION = (
    "Answer the question using only the supplied context. "
    "If the context is insufficient, say that you cannot answer from it. "
    "Do not claim evidence outside the supplied context."
)


def supported_context(
    model_limit: object,
    tokenizer_limit: object,
) -> int:
    """Return the smaller valid limit while ignoring tokenizer sentinels."""
    if (
        not isinstance(model_limit, int)
        or isinstance(model_limit, bool)
        or model_limit <= 0
    ):
        raise ValueError("model context limit must be a positive integer")
    if (
        isinstance(tokenizer_limit, int)
        and not isinstance(tokenizer_limit, bool)
        and 0 < tokenizer_limit < _SENTINEL_CONTEXT
    ):
        return min(model_limit, tokenizer_limit)
    return model_limit


class QwenGenerator:
    """Lazily load the verified Qwen tokenizer and CPU model."""

    def __init__(
        self,
        cache_directory: Path,
        local_files_only: bool = False,
        show_progress: bool = False,
        progress_position: int = 0,
        progress_leave: bool = True,
    ) -> None:
        """Store runtime configuration without loading model assets."""
        self._cache_directory = cache_directory
        self._local_files_only = local_files_only
        self._show_progress = show_progress
        self._progress_position = progress_position
        self._progress_leave = progress_leave
        self._config: Any | None = None
        self._tokenizer: Any | None = None
        self._model: Any | None = None

    @property
    def supported_context_tokens(self) -> int:
        """Load lightweight metadata/tokenizer and return the safe limit."""
        self._load_tokenizer()
        assert self._config is not None
        assert self._tokenizer is not None
        return supported_context(
            self._config.max_position_embeddings,
            self._tokenizer.model_max_length,
        )

    def count_prompt_tokens(self, question: str, context: str) -> int:
        """Count the exact no-thinking template used for generation."""
        self._load_tokenizer()
        assert self._tokenizer is not None
        token_ids = self._tokenizer.apply_chat_template(
            self._messages(question, context),
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        return len(token_ids)

    def generate(
        self,
        question: str,
        context: str,
        max_new_tokens: int,
    ) -> str:
        """Generate only answer text with the verified greedy CPU runtime."""
        self._load_tokenizer()
        try:
            import torch
            from transformers import AutoModelForCausalLM

            if self._model is None:
                torch.set_num_threads(4)
                model_factory: Any = AutoModelForCausalLM
                with self._phase("Loading Qwen model") as progress:
                    model = model_factory.from_pretrained(
                        MODEL_ID,
                        revision=MODEL_REVISION,
                        cache_dir=self._cache_directory,
                        local_files_only=self._local_files_only,
                        trust_remote_code=False,
                        dtype=torch.float32,
                    )
                    progress.update()
                self._model = model.eval()
            assert self._tokenizer is not None
            inputs = self._tokenizer.apply_chat_template(
                self._messages(question, context),
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
                return_dict=True,
                return_tensors="pt",
            )
            prompt_tokens = inputs["input_ids"].shape[-1]
            if prompt_tokens + max_new_tokens > self.supported_context_tokens:
                raise ValueError(
                    "complete prompt plus answer exceeds supported context"
                )
            with self._phase(
                "Generating answer",
                total=max_new_tokens,
                unit="tok",
            ) as progress:
                with torch.inference_mode():
                    output = self._model.generate(
                        **inputs,
                        max_new_tokens=max_new_tokens,
                        streamer=_ProgressStreamer(
                            progress,
                            prompt_tokens,
                        ),
                        do_sample=False,
                        temperature=None,
                        top_p=None,
                        top_k=None,
                        pad_token_id=self._tokenizer.eos_token_id,
                    )
            answer_ids = output[0, prompt_tokens:]
            return str(
                self._tokenizer.decode(
                    answer_ids,
                    skip_special_tokens=True,
                )
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise RuntimeError(f"Qwen generation failed: {error}") from error

    def _load_tokenizer(self) -> None:
        """Load config/tokenizer once without loading model weights."""
        if self._tokenizer is not None:
            return
        try:
            from transformers import AutoConfig, AutoTokenizer

            options = {
                "revision": MODEL_REVISION,
                "cache_dir": self._cache_directory,
                "local_files_only": self._local_files_only,
                "trust_remote_code": False,
            }
            tokenizer_factory: Any = AutoTokenizer
            with self._phase("Loading Qwen tokenizer") as progress:
                self._config = AutoConfig.from_pretrained(MODEL_ID, **options)
                self._tokenizer = tokenizer_factory.from_pretrained(
                    MODEL_ID, **options
                )
                progress.update()
        except (OSError, RuntimeError, ValueError) as error:
            raise RuntimeError(
                f"Could not load Qwen tokenizer: {error}"
            ) from error

    def _phase(
        self,
        description: str,
        total: int = 1,
        unit: str = "phase",
    ) -> Any:
        """Create one opt-in stderr progress phase."""
        return tqdm(
            total=total,
            desc=description,
            unit=unit,
            position=self._progress_position,
            leave=self._progress_leave,
            disable=not self._show_progress,
        )

    @staticmethod
    def _messages(question: str, context: str) -> list[dict[str, str]]:
        """Build the single real template shared by counting/generation."""
        return [
            {"role": "system", "content": _SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion:\n{question}",
            },
        ]


class _ProgressStreamer:
    """Update tqdm from Transformers' generation streamer hook."""

    def __init__(self, progress: Any, prompt_tokens: int) -> None:
        self._progress = progress
        self._prompt_tokens_to_skip = prompt_tokens

    def put(self, value: Any) -> None:
        """Count generated tokens while skipping the prompt echo."""
        token_count = int(value.numel()) if hasattr(value, "numel") else 1
        skipped = min(token_count, self._prompt_tokens_to_skip)
        self._prompt_tokens_to_skip -= skipped
        generated = token_count - skipped
        if generated:
            self._progress.update(generated)

    def end(self) -> None:
        """Satisfy the Transformers streamer protocol."""
