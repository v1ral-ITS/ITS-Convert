"""AI Code Review integration with codepolisher-cli."""
from __future__ import annotations

import subprocess
import json
from pathlib import Path
from typing import Optional

class CodeReviewError(Exception):
    """Error during code review."""
    pass

class CodeReviewer:
    """
    Integrate with codepolisher-cli for AI-powered code review.

    This class provides a Python interface to run codepolisher-cli
    on files before or after building.
    """

    def __init__(self, provider: str = "ollama", model: str = "llama3.2"):
        """
        Initialize the code reviewer.

        Args:
            provider: AI provider to use (openai, anthropic, gemini, ollama, etc.)
            model: Model to use for review
        """
        self.provider = provider
        self.model = model

    def review(self, file_path: Path, **kwargs) -> dict:
        """
        Run AI code review on a file.

        Args:
            file_path: Path to the file to review
            **kwargs: Additional arguments to pass to codepolisher

        Returns:
            Dictionary with review results
        """
        if not self._is_codepolisher_available():
            raise CodeReviewError(
                "codepolisher-cli not found. Please install with: npm install -g codepolisher-cli"
            )

        cmd = ["codepolisher", "review", str(file_path)]

        if "language" in kwargs:
            cmd.extend(["--language", kwargs["language"]])
        if "focus" in kwargs:
            cmd.extend(["--focus", kwargs["focus"]])
        if "rules" in kwargs:
            cmd.extend(["--rules", kwargs["rules"]])
        if "output" in kwargs:
            cmd.extend(["--output", kwargs["output"]])
        if "strict" in kwargs and kwargs["strict"]:
            cmd.append("--strict")
        if "security" in kwargs and kwargs["security"]:
            cmd.append("--security")
        if "save_as" in kwargs:
            cmd.extend(["--save-as", kwargs["save_as"]])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            try:
                error_data = json.loads(result.stdout)
                return {
                    "success": False,
                    "error": error_data.get("error", result.stderr),
                    "exit_code": result.returncode,
                }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout,
                    "exit_code": result.returncode,
                }

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": True,
                "output": result.stdout,
                "exit_code": result.returncode,
            }

    def review_batch(self, files: list[Path], **kwargs) -> list[dict]:
        """
        Run AI code review on multiple files.

        Args:
            files: List of file paths to review
            **kwargs: Additional arguments to pass to codepolisher

        Returns:
            List of review results for each file
        """
        results = []
        for file_path in files:
            try:
                result = self.review(file_path, **kwargs)
                results.append({
                    "file": str(file_path),
                    "result": result,
                })
            except Exception as e:
                results.append({
                    "file": str(file_path),
                    "error": str(e),
                })
        return results

    def review_and_fix(self, file_path: Path, output_file: Optional[Path] = None, **kwargs) -> Path:
        """
        Run AI code review and save the fixed version.

        Args:
            file_path: Path to the file to review
            output_file: Where to save the fixed version
            **kwargs: Additional arguments to pass to codepolisher

        Returns:
            Path to the fixed file
        """
        if output_file is None:
            output_file = file_path.parent / f"{file_path.stem}.polished{file_path.suffix}"

        kwargs["save_as"] = str(output_file)

        result = self.review(file_path, **kwargs)

        if output_file.exists():
            return output_file

        raise CodeReviewError(f"Fixed file not created: {output_file}")

    def _is_codepolisher_available(self) -> bool:
        """Check if codepolisher-cli is installed."""
        import shutil
        return shutil.which("codepolisher") is not None
