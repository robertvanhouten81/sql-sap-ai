from typing import Dict, Any
from anthropic import Anthropic
import os
import logging
import json

logger = logging.getLogger(__name__)

class PromptClassifier:
    def __init__(self):
        self.client = Anthropic()  # Will use ANTHROPIC_API_KEY env var by default
        logger.info("PromptClassifier initialized")
        
    def classify_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Determine if the prompt is requesting SQL data or asking a general question.
        Also checks if it's a follow-up question to a previous query.
        
        Args:
            prompt (str): The user's input prompt
            
        Returns:
            Dict containing:
            - type: "sql" or "general"
            - is_followup: boolean indicating if this is a follow-up question
            - context: any relevant context for follow-up questions
        """
        system_prompt = """Analyze if the given prompt is requesting SQL data or asking a general question.
        Consider:
        1. SQL indicators: mentions of data, statistics, numbers, comparisons, or specific database fields
        2. Follow-up indicators: references to previous queries, use of pronouns like "it", "that", "those"
        3. Time references that might modify previous queries
        
        Respond with JSON only, no other text:
        {
            "type": "sql" or "general",
            "is_followup": true/false,
            "context": "relevant context for follow-ups or null"
        }"""
        
        try:
            logger.info({
                "agent": "PromptClassifier",
                "action": "analyzing_prompt",
                "prompt": prompt
            })
            
            message = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract and parse the JSON response
            try:
                response_text = message.content[0].text
                result = json.loads(response_text)
                
                logger.info({
                    "agent": "PromptClassifier",
                    "action": "classification_complete",
                    "result": {
                        "type": result["type"],
                        "is_followup": result["is_followup"],
                        "has_context": result["context"] is not None
                    }
                })
                
                return result
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                error_msg = f"Failed to parse Claude response: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {
                    "error": error_msg,
                    "type": "general",
                    "is_followup": False,
                    "context": None
                }
            
        except Exception as e:
            error_msg = f"Classification failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "error": error_msg,
                "type": "general",
                "is_followup": False,
                "context": None
            }
