import unittest

from app.services.question_generation_service import (
    _parse_qwen_generated_response,
    _validate_qwen_split,
)


class QwenQuestionGenerationParserTests(unittest.TestCase):
    def test_missing_area_is_inferred_from_question_text(self):
        result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "Explain how you used MongoDB in your resume screening project.",
                        "difficulty": "medium",
                        "expectedAnswer": "Candidate should explain schema design, storing candidate records, querying, and persistence.",
                    }
                ]
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "Database")
        self.assertEqual(result["questions"][0]["source"], "qwen_generated")

    def test_area_alias_maps_to_area_of_expertise(self):
        result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "How would you design a FastAPI service for interview scoring?",
                        "area": "FastAPI",
                        "difficulty": "easy",
                        "expectedAnswer": "Candidate should cover routing, validation, service boundaries, and persistence.",
                    }
                ]
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "FastAPI")

    def test_topic_alias_maps_to_area_of_expertise(self):
        result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "How did you use React state in the interview configuration page?",
                        "topic": "React",
                        "difficulty": "easy",
                        "expectedAnswer": "Candidate should discuss state updates, validation, and conditional UI.",
                    }
                ]
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "React")

    def test_complete_question_passes_unchanged(self):
        result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "Describe how your AI ranking model evaluates resumes.",
                        "areaOfExpertise": "AI/ML",
                        "difficulty": "hard",
                        "expectedAnswer": "Candidate should explain features, matching logic, weighting, and evaluation.",
                        "source": "qwen_generated",
                    }
                ]
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "AI/ML")
        self.assertEqual(result["questions"][0]["difficulty"], "hard")

    def test_markdown_fenced_generated_questions_still_parse(self):
        result = _parse_qwen_generated_response(
            """
```json
{
  "generatedQuestions": [
    {
      "question": "How would you build a FastAPI API for screening resumes?",
      "areaOfExpertise": "FastAPI",
      "difficulty": "medium",
      "expectedAnswer": "Candidate should cover endpoints, validation, ranking orchestration, and persistence.",
      "source": "qwen_generated"
    }
  ]
}
```
"""
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "FastAPI")

    def test_direct_array_still_parses(self):
        result = _parse_qwen_generated_response(
            [
                {
                    "question": "How would you rank resumes semantically for an ATS workflow?",
                    "difficulty": "hard",
                    "expectedAnswer": "Candidate should discuss embeddings or semantic similarity, scoring, and ranking tradeoffs.",
                }
            ]
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["questions"][0]["areaOfExpertise"], "Resume Screening")

    def test_missing_expected_answer_is_rejected(self):
        result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "Explain how you used MongoDB in your resume screening project.",
                        "difficulty": "medium",
                    }
                ]
            }
        )

        self.assertFalse(result["success"])
        self.assertIn("missing expectedAnswer", result["message"])

    def test_wrong_difficulty_split_is_rejected_by_split_validator(self):
        parse_result = _parse_qwen_generated_response(
            {
                "questions": [
                    {
                        "question": "Explain the MongoDB schema used for candidate records.",
                        "difficulty": "easy",
                        "expectedAnswer": "Candidate should discuss collections, fields, indexes, and queries.",
                    }
                ]
            }
        )

        self.assertTrue(parse_result["success"])
        self.assertEqual(
            _validate_qwen_split(parse_result["questions"], {"easy": 0, "medium": 1, "hard": 0}),
            "Qwen returned 1 easy questions; expected 0.",
        )


if __name__ == "__main__":
    unittest.main()
