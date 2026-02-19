"""
字幕质量AI评估测试脚本
支持多种AI后端：OpenAI、DeepSeek、本地模型等
"""
import asyncio
import sys
import os
import re
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.thunder_subtitle_cli.client import ThunderClient


def extract_text_from_srt(content: str) -> str:
    """从SRT格式中提取纯文本"""
    lines = content.split('\n')
    text_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if '-->' in line:
            continue
        text_lines.append(line)
    
    return '\n'.join(text_lines)


def extract_text_from_ass(content: str) -> str:
    """从ASS格式中提取纯文本"""
    lines = content.split('\n')
    text_lines = []
    in_events = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith('[Events]'):
            in_events = True
            continue
        
        if line.startswith('[') and in_events:
            break
        
        if in_events and line.startswith('Dialogue:'):
            parts = line.split(',', 9)
            if len(parts) >= 10:
                text = parts[9]
                text = re.sub(r'\{[^}]*\}', '', text)
                text = re.sub(r'\\N', '\n', text)
                text = text.strip()
                if text:
                    text_lines.append(text)
    
    return '\n'.join(text_lines)


def extract_text(content: str, ext: str) -> str:
    """根据扩展名提取文本"""
    ext = ext.lower().lstrip('.')
    if ext == 'ass':
        return extract_text_from_ass(content)
    else:
        return extract_text_from_srt(content)


class AIQualityEvaluator:
    """AI质量评估器基类"""
    
    async def evaluate(self, text: str) -> dict:
        raise NotImplementedError


class OpenAIEvaluator(AIQualityEvaluator):
    """OpenAI API评估器"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model
    
    async def evaluate(self, text: str) -> dict:
        if not self.api_key:
            return {"error": "未配置OpenAI API Key", "available": False}
        
        try:
            import aiohttp
            
            prompt = f"""请评估以下字幕文本的翻译质量。

字幕文本（前1000字符）:
{text[:1000]}

请从以下维度评估，每项0-10分：
1. 流畅度：语句是否通顺自然
2. 准确度：翻译是否准确传达原意
3. 本地化：是否符合中文表达习惯
4. 专业性：专业术语翻译是否恰当

请以JSON格式返回结果：
{{
    "fluency": 分数,
    "accuracy": 分数,
    "localization": 分数,
    "professionalism": 分数,
    "overall_score": 综合分数(0-100),
    "is_machine_translation": true/false,
    "issues": ["问题1", "问题2"],
    "summary": "简短评价"
}}"""

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "你是一个专业的字幕翻译质量评估专家。请客观评估字幕质量，识别机器翻译痕迹。"},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        return {"error": f"API请求失败: {response.status}", "available": False}
                    
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        result = json.loads(json_match.group())
                        result["available"] = True
                        return result
                    else:
                        return {"error": "无法解析AI响应", "raw": content, "available": False}
                        
        except Exception as e:
            return {"error": str(e), "available": False}


class DeepSeekEvaluator(AIQualityEvaluator):
    """DeepSeek API评估器"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1"
    
    async def evaluate(self, text: str) -> dict:
        if not self.api_key:
            return {"error": "未配置DeepSeek API Key", "available": False}
        
        evaluator = OpenAIEvaluator(
            api_key=self.api_key,
            base_url=self.base_url,
            model="deepseek-chat"
        )
        return await evaluator.evaluate(text)


class LocalModelEvaluator(AIQualityEvaluator):
    """本地模型评估器（使用transformers）"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
    
    def _load_model(self):
        try:
            from transformers import pipeline
            if self.model is None:
                print("正在加载本地模型...")
                self.model = pipeline(
                    "text-classification",
                    model="bert-base-chinese",
                    device=-1
                )
            return True
        except ImportError:
            return False
        except Exception as e:
            print(f"加载模型失败: {e}")
            return False
    
    async def evaluate(self, text: str) -> dict:
        if not self._load_model():
            return {"error": "无法加载本地模型，请安装transformers", "available": False}
        
        try:
            sentences = text.split('\n')[:20]
            results = []
            
            for sentence in sentences:
                if len(sentence.strip()) > 5:
                    result = self.model(sentence[:512])
                    results.append(result[0] if result else None)
            
            if not results:
                return {"error": "无有效文本", "available": False}
            
            avg_score = sum(r.get('score', 0.5) for r in results if r) / len(results)
            
            return {
                "available": True,
                "overall_score": round(avg_score * 100, 2),
                "fluency": round(avg_score * 10, 1),
                "summary": "基于本地BERT模型评估"
            }
        except Exception as e:
            return {"error": str(e), "available": False}


class RuleBasedEvaluator(AIQualityEvaluator):
    """基于规则的评估器（无需API）"""
    
    async def evaluate(self, text: str) -> dict:
        issues = []
        scores = {
            "fluency": 7.0,
            "accuracy": 7.0,
            "localization": 7.0,
            "professionalism": 7.0
        }
        
        mt_patterns = [
            (r'的{3,}', '连续多个"的"', -1),
            (r'了{3,}', '连续多个"了"', -1),
            (r'是{3,}', '连续多个"是"', -1),
            (r'我我我|你你你|他他他', '重复代词', -1.5),
            (r'[，。、]{2,}', '连续标点', -0.5),
        ]
        
        for pattern, desc, penalty in mt_patterns:
            matches = re.findall(pattern, text)
            if matches:
                issues.append(f"{desc}: {len(matches)}次")
                scores["fluency"] += penalty
        
        unnatural = ['打开灯', '关闭灯', '这是非常', '那是非常', '在这一点上']
        for phrase in unnatural:
            if phrase in text:
                issues.append(f"不自然表达: {phrase}")
                scores["localization"] -= 1
        
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len([c for c in text if not c.isspace()])
        chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
        
        if chinese_ratio < 0.5:
            scores["accuracy"] -= 2
            issues.append(f"中文比例过低: {chinese_ratio:.1%}")
        
        punct_count = len(re.findall(r'[，。！？、]', text))
        punct_ratio = punct_count / total_chars if total_chars > 0 else 0
        
        if punct_ratio < 0.01:
            scores["fluency"] -= 1
            issues.append("缺少标点符号")
        
        for key in scores:
            scores[key] = max(0, min(10, scores[key]))
        
        overall = sum(scores.values()) / len(scores) * 10
        
        is_mt = overall < 60 or len(issues) > 3
        
        return {
            "available": True,
            "fluency": round(scores["fluency"], 1),
            "accuracy": round(scores["accuracy"], 1),
            "localization": round(scores["localization"], 1),
            "professionalism": round(scores["professionalism"], 1),
            "overall_score": round(overall, 2),
            "is_machine_translation": is_mt,
            "issues": issues,
            "summary": "基于规则评估" + ("，疑似机器翻译" if is_mt else "")
        }


async def test_with_evaluator(evaluator: AIQualityEvaluator, evaluator_name: str, text: str) -> dict:
    """使用指定评估器测试"""
    print(f"\n使用 {evaluator_name} 评估中...")
    start_time = time.time()
    
    result = await evaluator.evaluate(text)
    
    elapsed = time.time() - start_time
    result["evaluator"] = evaluator_name
    result["elapsed_time"] = round(elapsed, 2)
    
    return result


async def main():
    print("=" * 70)
    print("字幕质量AI评估测试")
    print("=" * 70)
    
    print("\n请选择AI评估方案：")
    print("1. OpenAI API (需要API Key)")
    print("2. DeepSeek API (需要API Key)")
    print("3. 本地模型 (需要安装transformers)")
    print("4. 规则评估 (无需API)")
    print("5. 全部测试")
    
    choice = input("\n请输入选项 (1-5): ").strip()
    
    print("\n正在搜索字幕...")
    client = ThunderClient()
    results = await client.search(query="ipx580")
    
    if not results:
        print("未找到字幕")
        return
    
    print(f"找到 {len(results)} 个字幕")
    
    print("\n正在下载第一个字幕...")
    subtitle = results[0]
    content_bytes = await client.download_bytes(url=subtitle.url, timeout_s=30)
    
    try:
        content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        content = content_bytes.decode('gbk', errors='ignore')
    
    text = extract_text(content, subtitle.ext)
    
    print(f"\n字幕: {subtitle.name}")
    print(f"文本长度: {len(text)} 字符")
    print(f"\n文本预览 (前500字符):")
    print("-" * 50)
    print(text[:500])
    print("-" * 50)
    
    evaluators = []
    
    if choice in ['1', '5']:
        evaluators.append((OpenAIEvaluator(), "OpenAI"))
    if choice in ['2', '5']:
        evaluators.append((DeepSeekEvaluator(), "DeepSeek"))
    if choice in ['3', '5']:
        evaluators.append((LocalModelEvaluator(), "本地模型"))
    if choice in ['4', '5']:
        evaluators.append((RuleBasedEvaluator(), "规则评估"))
    
    if not evaluators:
        print("无效选项")
        return
    
    print("\n" + "=" * 70)
    print("开始评估")
    print("=" * 70)
    
    all_results = []
    
    for evaluator, name in evaluators:
        result = await test_with_evaluator(evaluator, name, text)
        all_results.append(result)
        
        print(f"\n{'='*50}")
        print(f"评估器: {name}")
        print(f"耗时: {result.get('elapsed_time', 0)}秒")
        
        if result.get("available"):
            print(f"\n📊 评估结果:")
            print(f"  流畅度: {result.get('fluency', 'N/A')}/10")
            print(f"  准确度: {result.get('accuracy', 'N/A')}/10")
            print(f"  本地化: {result.get('localization', 'N/A')}/10")
            print(f"  专业性: {result.get('professionalism', 'N/A')}/10")
            print(f"\n  ★ 综合评分: {result.get('overall_score', 'N/A')}/100")
            print(f"  ★ 疑似机器翻译: {'是' if result.get('is_machine_translation') else '否'}")
            
            if result.get('issues'):
                print(f"\n  发现的问题:")
                for issue in result['issues'][:5]:
                    print(f"    - {issue}")
            
            print(f"\n  评价: {result.get('summary', 'N/A')}")
        else:
            print(f"\n❌ 评估失败: {result.get('error', '未知错误')}")
    
    print("\n" + "=" * 70)
    print("评估汇总")
    print("=" * 70)
    
    available_results = [r for r in all_results if r.get("available")]
    
    if available_results:
        print(f"\n{'评估器':<15} {'评分':<10} {'MT判定':<10} {'耗时'}")
        print("-" * 50)
        for r in available_results:
            mt_str = "是" if r.get('is_machine_translation') else "否"
            print(f"{r['evaluator']:<15} {r.get('overall_score', 'N/A'):<10} {mt_str:<10} {r.get('elapsed_time', 0)}s")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
