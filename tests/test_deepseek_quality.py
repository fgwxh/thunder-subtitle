"""
字幕质量DeepSeek AI评估测试脚本
使用OpenAI库调用DeepSeek API
"""
import asyncio
import sys
import os
import re
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.thunder_subtitle_cli.client import ThunderClient
from openai import OpenAI


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


def evaluate_with_deepseek(text: str, client: OpenAI) -> dict:
    """使用DeepSeek API评估字幕质量"""
    try:
        prompt = f"""请评估以下字幕文本的翻译质量。

字幕文本（前1500字符）:
{text[:1500]}

请从以下维度评估，每项0-10分：
1. 流畅度：语句是否通顺自然，是否符合中文表达习惯
2. 准确度：翻译是否准确传达原意，有无误译
3. 本地化：是否自然流畅，有无机器翻译痕迹
4. 专业性：专业术语翻译是否恰当

请判断这是否为机器翻译的字幕。

请以JSON格式返回结果（不要包含其他内容）：
{{
    "fluency": 分数,
    "accuracy": 分数,
    "localization": 分数,
    "professionalism": 分数,
    "overall_score": 综合分数(0-100),
    "is_machine_translation": true或false,
    "confidence": 置信度(0-1),
    "issues": ["问题1", "问题2"],
    "summary": "简短评价（50字以内）"
}}"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的字幕翻译质量评估专家。请客观评估字幕质量，识别机器翻译痕迹。只返回JSON格式的结果。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            result["available"] = True
            return result
        else:
            return {"error": "无法解析AI响应", "raw": content, "available": False}
                    
    except Exception as e:
        return {"error": str(e), "available": False}


async def main():
    print("=" * 70)
    print("字幕质量DeepSeek AI评估测试")
    print("=" * 70)
    
    # 从环境变量获取API密钥
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("请设置环境变量 DEEPSEEK_API_KEY")
        return
    
    client_ai = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    print("\n正在搜索字幕...")
    client = ThunderClient()
    results = await client.search(query="ipx580")
    
    if not results:
        print("未找到字幕")
        return
    
    print(f"找到 {len(results)} 个字幕")
    
    all_results = []
    
    for i, subtitle in enumerate(results[:5]):
        print(f"\n{'='*70}")
        print(f"字幕 #{i+1}: {subtitle.name}")
        print(f"扩展名: {subtitle.ext}")
        print("-" * 70)
        
        try:
            print("正在下载字幕内容...")
            content_bytes = await client.download_bytes(url=subtitle.url, timeout_s=30)
            
            try:
                content = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                content = content_bytes.decode('gbk', errors='ignore')
            
            text = extract_text(content, subtitle.ext)
            
            print(f"文本长度: {len(text)} 字符")
            print(f"\n文本预览 (前300字符):")
            print("-" * 50)
            print(text[:300])
            print("-" * 50)
            
            print("\n正在使用DeepSeek AI评估...")
            start_time = time.time()
            
            result = evaluate_with_deepseek(text, client_ai)
            
            elapsed = time.time() - start_time
            
            if result.get("available"):
                print(f"\n📊 AI评估结果 (耗时: {elapsed:.1f}秒):")
                print(f"  流畅度: {result.get('fluency', 'N/A')}/10")
                print(f"  准确度: {result.get('accuracy', 'N/A')}/10")
                print(f"  本地化: {result.get('localization', 'N/A')}/10")
                print(f"  专业性: {result.get('professionalism', 'N/A')}/10")
                print(f"\n  ★ 综合评分: {result.get('overall_score', 'N/A')}/100")
                print(f"  ★ 疑似机器翻译: {'是' if result.get('is_machine_translation') else '否'}")
                print(f"  ★ 置信度: {result.get('confidence', 'N/A')}")
                
                if result.get('issues'):
                    print(f"\n  发现的问题:")
                    for issue in result['issues'][:5]:
                        print(f"    - {issue}")
                
                print(f"\n  AI评价: {result.get('summary', 'N/A')}")
                
                all_results.append({
                    'name': subtitle.name,
                    'ext': subtitle.ext,
                    'score': result.get('overall_score', 0),
                    'is_mt': result.get('is_machine_translation', False),
                    'confidence': result.get('confidence', 0),
                    'fluency': result.get('fluency', 0),
                    'summary': result.get('summary', '')
                })
            else:
                print(f"\n❌ 评估失败: {result.get('error', '未知错误')}")
                all_results.append({
                    'name': subtitle.name,
                    'ext': subtitle.ext,
                    'score': 0,
                    'is_mt': False,
                    'confidence': 0,
                    'fluency': 0,
                    'summary': result.get('error', '评估失败')
                })
                
        except Exception as e:
            print(f"❌ 处理失败: {e}")
            all_results.append({
                'name': subtitle.name,
                'ext': subtitle.ext,
                'score': 0,
                'is_mt': False,
                'confidence': 0,
                'fluency': 0,
                'summary': str(e)
            })
    
    print("\n" + "=" * 70)
    print("📋 评估汇总 (按评分排序)")
    print("=" * 70)
    
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n{'排名':<4} {'评分':<8} {'MT判定':<8} {'置信度':<8} {'文件名'}")
    print("-" * 70)
    for i, r in enumerate(all_results):
        mt_str = "是" if r['is_mt'] else "否"
        print(f"{i+1:<4} {r['score']:<8.1f} {mt_str:<8} {r['confidence']:<8.1f} {r['name'][:40]}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
