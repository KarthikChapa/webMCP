import os
import logging
import re
import time
from openai import OpenAI

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

last_request_time = 0
request_count = 0

def clean_json_response(response_text: str) -> str:
    if not response_text:
        return response_text
    
    response_text = re.sub(r'```json\s*', '', response_text)
    response_text = re.sub(r'```\s*', '', response_text)
    response_text = response_text.strip()
    
    return response_text

def smart_rate_limit():
    global last_request_time, request_count
    
    current_time = time.time()
    
    if current_time - last_request_time > 60:
        request_count = 0
        last_request_time = current_time
    
    if request_count >= 3: 
        time_elapsed = current_time - last_request_time
        if time_elapsed < 60:
            min_wait = max(16, 60 - time_elapsed + 1)
            logger.info(f"Smart rate limit: waiting {min_wait:.1f} seconds...")
            time.sleep(min_wait)
            request_count = 0
            last_request_time = time.time()

def get_llm_response(system_prompt: str, user_prompt: str, is_final_answer_generation: bool = False) -> str:
    
    model_options = [
        {
            "name": "google/gemini-2.0-flash-exp:free",
            "rate_limit": 4,
            "use_rate_limiting": True, 
            "description": "Gemini 2.0 Flash (PRIMARY - User Requested)",
            "priority": 1
        },
        {
            "name": "mistralai/mistral-7b-instruct:free",
            "rate_limit": 20,
            "use_rate_limiting": False, 
            "description": "Mistral 7B Instruct (SECONDARY - reliable)",
            "priority": 2
        },
        {
            "name": "meta-llama/llama-3.2-3b-instruct:free", 
            "rate_limit": 20,
            "use_rate_limiting": False,
            "description": "Meta Llama 3.2 (TERTIARY - good general, 20/min)",
            "priority": 3
        },
        {
            "name": "deepseek/deepseek-r1-0528-qwen3-8b:free",
            "rate_limit": 20, 
            "use_rate_limiting": False, 
            "description": "DeepSeek R1 Qwen3 8B (FALLBACK - high rate limit, 20/min)",
            "priority": 4
        }
    ]
        
    for model_config in model_options:
        model_name = model_config["name"]
        
        try:
            if model_config["use_rate_limiting"]:
                smart_rate_limit()
            
            logger.info(f"Using OpenRouter model: {model_name} (Priority {model_config['priority']}) {'for final answer' if is_final_answer_generation else ''}")
            
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY,
            )
            
            response = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://webmcp-automation.local",
                    "X-Title": "WebMCP Browser Automation",
                },
                extra_body={},
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2 if is_final_answer_generation else 0.1, 
                max_tokens=2000,
            )
            
            if model_config["use_rate_limiting"]:
                global request_count
                request_count += 1
            
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    cleaned_content = content.strip() if is_final_answer_generation else clean_json_response(content)
                    logger.info(f"✅ Success from {model_name}")
                    return cleaned_content
            
            logger.warning(f"Empty response from {model_name}, trying next model")
            continue
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                logger.warning(f"🔄 Rate limit for {model_name}, switching to next model")
                continue
            elif "401" in error_msg or "Unauthorized" in error_msg:
                logger.error(f"❌ Auth failed for {model_name}")
                continue
            elif "insufficient_quota" in error_msg.lower():
                logger.warning(f"💰 Quota exhausted for {model_name}, trying next model")
                continue
            else:
                logger.error(f"❌ Error with {model_name}: {error_msg}")
                continue
    
    logger.error("❌ All OpenRouter models failed!")
    return None

def test_mcp_models():
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY not found")
        return False
    
    print("🧪 Testing Models for MCP Compatibility (Gemini Flash 2.0 Primary)...")
    print("="*70)
    print("🎯 OPTIMIZED ORDER FOR MCP (GEMINI FLASH 2.0 PRIMARY):")
    print("   1. Google Gemini 2.0 Flash (PRIMARY - User Requested)")
    print("   2. Mistral 7B Instruct (SECONDARY - reliable)")
    print("   3. Meta Llama 3.2 (TERTIARY - 20/min)")
    print("   4. DeepSeek R1 Qwen3 8B (FALLBACK - high rate limit)")
    print("="*70)
    
    test_system_prompt = """You are an AI that controls web browsers. Output ONLY valid JSON arrays with "action_type" and "parameters" fields.

EXAMPLE:
[{"action_type": "navigate", "parameters": {"url": "https://www.google.com"}}]

No other text allowed."""
    test_user_prompt = "Navigate to google.com. Return ONLY the JSON array."
    
    success_count = 0
    total_time = time.time()
    
    for i in range(4):
        print(f"\n🔄 MCP Test {i+1}/4:")
        start_time = time.time()
        result = get_llm_response(test_system_prompt, test_user_prompt)
        request_time = time.time() - start_time
        
        if result:
            try:
                import json
                parsed = json.loads(result)
                if isinstance(parsed, list) and len(parsed) > 0 and "action_type" in parsed[0] and "parameters" in parsed[0]:
                    print(f"✅ MCP Success in {request_time:.1f}s: Valid MCP format")
                    success_count += 1
                else:
                    print(f"⚠️  Valid JSON but wrong MCP format: {result[:70]}...")
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON: {result[:70]}...")
        else:
            print(f"❌ No response after {request_time:.1f}s")
    
    total_time = time.time() - total_time
    print(f"\n📊 MCP Compatibility Results (Gemini Flash 2.0 Primary):")
    print(f"   MCP Success rate: {success_count}/4 ({success_count/4*100:.1f}%)")
    print(f"   Total time: {total_time:.1f} seconds")
    
    if success_count >= 2:
        print("🎉 Good MCP compatibility with Gemini Flash 2.0 - ready for demo!")
        return True
    else:
        print("⚠️  MCP compatibility could be improved. Check model responses.")
        return False

if __name__ == "__main__":
    print("🚀 WebMCP LLM Client Test (Gemini Flash 2.0 Primary)")
    success = test_mcp_models()
    if success:
        print("\n🎬 Ready for reliable MCP demo video with Gemini Flash 2.0!")
    else:
        print("\n⚠️  Review Gemini Flash 2.0 performance for MCP tasks.")