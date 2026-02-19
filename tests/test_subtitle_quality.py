"""
字幕质量评估测试脚本 v2
改进版：更好地处理SRT和ASS格式
"""
import asyncio
import sys
import os
import re
from collections import Counter
import math

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
        if re.match(r'^\d+$', line):
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
                text = re.sub(r'\\n', '\n', text)
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


def split_into_sentences(text: str) -> list:
    """将文本分割成句子"""
    sentences = re.split(r'[。！？!?\n]+', text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]


def calculate_perplexity(text: str) -> float:
    """
    计算困惑度（基于N-gram）
    困惑度越低，文本越自然
    """
    if len(text) < 10:
        return 100.0
    
    bigram_counts = Counter()
    for i in range(len(text) - 1):
        bigram = text[i:i+2]
        bigram_counts[bigram] += 1
    
    total_bigrams = sum(bigram_counts.values())
    if total_bigrams == 0:
        return 100.0
    
    perplexity = 0
    for count in bigram_counts.values():
        prob = count / total_bigrams
        perplexity -= prob * math.log2(prob)
    
    return round(2 ** perplexity, 2)


def analyze_fluency(text: str) -> dict:
    """分析文本流畅度"""
    sentences = split_into_sentences(text)
    
    if not sentences:
        return {
            'fluency_score': 0,
            'sentence_count': 0,
            'avg_sentence_length': 0,
            'vocabulary_richness': 0
        }
    
    sentence_lengths = [len(s) for s in sentences]
    avg_length = sum(sentence_lengths) / len(sentence_lengths)
    
    chars = [c for c in text if not c.isspace()]
    unique_chars = len(set(chars))
    total_chars = len(chars)
    vocabulary_richness = unique_chars / total_chars if total_chars > 0 else 0
    
    length_variance = 0
    if len(sentence_lengths) > 1:
        mean = avg_length
        length_variance = sum((l - mean) ** 2 for l in sentence_lengths) / len(sentence_lengths)
        length_variance = math.sqrt(length_variance)
    
    ideal_avg_length = 15
    length_score = max(0, 100 - abs(avg_length - ideal_avg_length) * 3)
    
    variance_score = max(0, 100 - length_variance * 2)
    
    fluency_score = (
        length_score * 0.3 +
        variance_score * 0.3 +
        vocabulary_richness * 100 * 0.2 +
        min(len(sentences) / 50 * 100, 100) * 0.2
    )
    
    return {
        'fluency_score': round(fluency_score, 2),
        'sentence_count': len(sentences),
        'avg_sentence_length': round(avg_length, 2),
        'length_std': round(length_variance, 2),
        'vocabulary_richness': round(vocabulary_richness, 4)
    }


def detect_machine_translation(text: str) -> dict:
    """检测机器翻译特征"""
    mt_indicators = []
    score = 0
    
    mt_patterns = [
        (r'的{3,}', '连续"的"', 15),
        (r'了{3,}', '连续"了"', 15),
        (r'是{3,}', '连续"是"', 15),
        (r'我我我', '重复代词', 20),
        (r'你你你', '重复代词', 20),
        (r'他他他', '重复代词', 20),
        (r'[，。、]{2,}', '连续标点', 10),
        (r'\s{4,}', '过多空格', 5),
    ]
    
    for pattern, desc, penalty in mt_patterns:
        matches = re.findall(pattern, text)
        if matches:
            mt_indicators.append(f"{desc}: {len(matches)}次")
            score += penalty * len(matches)
    
    unnatural_phrases = [
        '打开灯', '关闭灯', '打开门', '关闭门',
        '这是非常', '那是非常', '它是很',
        '在这一点上', '在某种程度上',
        '请让我', '请给我',
    ]
    
    found_unnatural = []
    for phrase in unnatural_phrases:
        count = text.count(phrase)
        if count > 0:
            found_unnatural.append(f"{phrase}: {count}次")
            score += 10 * count
    
    mt_probability = min(score / 100, 1.0)
    
    return {
        'mt_probability': round(mt_probability, 2),
        'mt_indicators': mt_indicators,
        'unnatural_phrases': found_unnatural
    }


def analyze_punctuation(text: str) -> dict:
    """分析标点符号使用"""
    chinese_punct = r'[，。！？、；：""''（）【】…—]'
    english_punct = r'[,.!?;:\"\'()\[\]]'
    
    cn_count = len(re.findall(chinese_punct, text))
    en_count = len(re.findall(english_punct, text))
    
    chars_no_space = len([c for c in text if not c.isspace()])
    
    total_punct = cn_count + en_count
    punct_ratio = total_punct / chars_no_space if chars_no_space > 0 else 0
    
    normal_ratio = 0.02 <= punct_ratio <= 0.10
    
    return {
        'chinese_punctuation': cn_count,
        'english_punctuation': en_count,
        'punctuation_ratio': round(punct_ratio, 4),
        'normal_ratio': normal_ratio
    }


def analyze_content_quality(text: str) -> dict:
    """分析内容质量"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len([c for c in text if not c.isspace()])
    
    chinese_ratio = chinese_chars / total_chars if total_chars > 0 else 0
    
    sentences = split_into_sentences(text)
    
    short_sentences = sum(1 for s in sentences if len(s) < 5)
    long_sentences = sum(1 for s in sentences if len(s) > 50)
    
    return {
        'chinese_ratio': round(chinese_ratio, 4),
        'total_chars': total_chars,
        'short_sentence_ratio': round(short_sentences / len(sentences), 2) if sentences else 0,
        'long_sentence_ratio': round(long_sentences / len(sentences), 2) if sentences else 0
    }


def calculate_overall_quality(subtitle_content: str, ext: str) -> dict:
    """综合评估字幕质量"""
    text = extract_text(subtitle_content, ext)
    
    if not text or len(text) < 10:
        return {'error': '文本内容太少', 'overall_score': 0, 'quality_level': '❌ 无效'}
    
    perplexity = calculate_perplexity(text)
    fluency = analyze_fluency(text)
    mt_detection = detect_machine_translation(text)
    punctuation = analyze_punctuation(text)
    content = analyze_content_quality(text)
    
    perplexity_score = max(0, 100 - perplexity)
    
    quality_score = (
        perplexity_score * 0.15 +
        fluency['fluency_score'] * 0.35 +
        (1 - mt_detection['mt_probability']) * 100 * 0.25 +
        (100 if punctuation['normal_ratio'] else 50) * 0.1 +
        content['chinese_ratio'] * 100 * 0.15
    )
    
    if quality_score >= 70:
        quality_level = '🟢 优质'
    elif quality_score >= 50:
        quality_level = '🟡 一般'
    elif quality_score >= 30:
        quality_level = '🟠 较差'
    else:
        quality_level = '🔴 很差'
    
    return {
        'text_length': len(text),
        'perplexity': perplexity,
        'fluency': fluency,
        'mt_detection': mt_detection,
        'punctuation': punctuation,
        'content': content,
        'overall_score': round(quality_score, 2),
        'quality_level': quality_level
    }


async def test_subtitle_quality():
    """测试字幕质量评估"""
    print("=" * 70)
    print("字幕质量评估测试 v2 - IPX-580")
    print("=" * 70)
    
    client = ThunderClient()
    
    print("\n正在搜索字幕...")
    results = await client.search(query="ipx580")
    
    if not results:
        print("未找到字幕")
        return
    
    print(f"找到 {len(results)} 个字幕\n")
    
    all_results = []
    
    for i, subtitle in enumerate(results[:10]):
        print(f"\n{'='*70}")
        print(f"字幕 #{i+1}: {subtitle.name}")
        print(f"语言: {', '.join(subtitle.languages) if subtitle.languages else '未知'}")
        print(f"扩展名: {subtitle.ext}")
        print("-" * 70)
        
        try:
            print("正在下载字幕内容...")
            content_bytes = await client.download_bytes(url=subtitle.url, timeout_s=30)
            
            try:
                content = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = content_bytes.decode('gbk')
                except UnicodeDecodeError:
                    content = content_bytes.decode('utf-8', errors='ignore')
            
            text = extract_text(content, subtitle.ext)
            
            print(f"\n提取的文本预览 (前300字符):")
            print("-" * 50)
            print(text[:300])
            print("-" * 50)
            
            quality = calculate_overall_quality(content, subtitle.ext)
            
            print(f"\n📊 质量评估结果:")
            print(f"  文本长度: {quality.get('text_length', 0)} 字符")
            print(f"  困惑度: {quality.get('perplexity', 0)} (越低越好)")
            
            fluency = quality.get('fluency', {})
            print(f"  流畅度: {fluency.get('fluency_score', 0)} 分")
            print(f"    - 句子数: {fluency.get('sentence_count', 0)}")
            print(f"    - 平均句长: {fluency.get('avg_sentence_length', 0)} 字")
            print(f"    - 词汇丰富度: {fluency.get('vocabulary_richness', 0)}")
            
            mt = quality.get('mt_detection', {})
            print(f"  机器翻译概率: {mt.get('mt_probability', 0):.0%}")
            if mt.get('mt_indicators'):
                print(f"    - MT特征: {', '.join(mt['mt_indicators'][:3])}")
            if mt.get('unnatural_phrases'):
                print(f"    - 不自然短语: {', '.join(mt['unnatural_phrases'][:3])}")
            
            punct = quality.get('punctuation', {})
            print(f"  标点符号: 中文{punct.get('chinese_punctuation', 0)}/英文{punct.get('english_punctuation', 0)}")
            print(f"    - 比例: {punct.get('punctuation_ratio', 0):.2%}")
            print(f"    - 正常: {'是' if punct.get('normal_ratio') else '否'}")
            
            content_info = quality.get('content', {})
            print(f"  中文比例: {content_info.get('chinese_ratio', 0):.1%}")
            
            print(f"\n  ★★★ 综合评分: {quality.get('overall_score', 0)} 分")
            print(f"  ★★★ 质量等级: {quality.get('quality_level', '未知')}")
            
            all_results.append({
                'name': subtitle.name,
                'ext': subtitle.ext,
                'score': quality.get('overall_score', 0),
                'level': quality.get('quality_level', '未知'),
                'mt_prob': mt.get('mt_probability', 0)
            })
            
        except Exception as e:
            print(f"❌ 下载或分析失败: {e}")
            all_results.append({
                'name': subtitle.name,
                'ext': subtitle.ext,
                'score': 0,
                'level': '❌ 错误',
                'mt_prob': 0
            })
    
    print("\n" + "=" * 70)
    print("📋 评分汇总 (按评分排序)")
    print("=" * 70)
    
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"{'排名':<4} {'评分':<8} {'MT概率':<8} {'等级':<10} {'文件名'}")
    print("-" * 70)
    for i, r in enumerate(all_results):
        print(f"{i+1:<4} {r['score']:<8.1f} {r['mt_prob']:<8.0%} {r['level']:<10} {r['name'][:40]}")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_subtitle_quality())
