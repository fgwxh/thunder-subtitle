"""
AI字幕质量评估模块
支持DeepSeek、OpenAI等API
"""
from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def calculate_filename_similarity(video_name: str, subtitle_name: str) -> float:
    """
    计算视频文件名与字幕文件名的匹配度
    返回 0-100 的分数
    """
    def normalize(name: str) -> str:
        name = name.lower()
        name = re.sub(r'\.(mp4|avi|mkv|mov|wmv|flv|webm|m4v|rmvb|rm|ts|m2ts|strm|srt|ass|ssa|sub)$', '', name)
        name = re.sub(r'[._\-\[\]()（）\s]+', ' ', name)
        name = re.sub(r'([a-z])(\d)', r'\1 \2', name)
        name = re.sub(r'(\d)([a-z])', r'\1 \2', name)
        name = re.sub(r'\s+', ' ', name).strip()
        return name
    
    video_norm = normalize(video_name)
    subtitle_norm = normalize(subtitle_name)
    
    if video_norm == subtitle_norm:
        return 100.0
    
    video_words = set(w for w in video_norm.split() if w)
    subtitle_words = set(w for w in subtitle_norm.split() if w)
    
    if not video_words or not subtitle_words:
        return 0.0
    
    common_words = video_words & subtitle_words
    similarity = len(common_words) / len(video_words) * 100
    
    year_pattern = r'(19\d{2}|20\d{2})'
    video_years = set(re.findall(year_pattern, video_norm))
    subtitle_years = set(re.findall(year_pattern, subtitle_norm))
    
    if video_years and subtitle_years:
        if video_years & subtitle_years:
            similarity += 10
        else:
            similarity -= 20
    
    if video_norm in subtitle_norm or subtitle_norm in video_norm:
        similarity = max(similarity, 80.0)
    
    video_alnum = re.sub(r'\s+', '', video_norm)
    subtitle_alnum = re.sub(r'\s+', '', subtitle_norm)
    if video_alnum == subtitle_alnum:
        similarity = 100.0
    elif video_alnum in subtitle_alnum or subtitle_alnum in video_alnum:
        similarity = max(similarity, 85.0)
    
    return min(100.0, max(0.0, similarity))


@dataclass
class QualityResult:
    """质量评估结果"""
    available: bool
    fluency: float
    accuracy: float
    localization: float
    professionalism: float
    overall_score: float
    is_machine_translation: bool
    confidence: float
    issues: list[str]
    summary: str
    error: Optional[str] = None
    elapsed_time: float = 0.0


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


class AIEvaluator:
    """AI质量评估器"""
    
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        enabled: bool = True
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.enabled = enabled and bool(api_key)
        self._client = None
    
    @property
    def client(self):
        if self._client is None and HAS_OPENAI and self.api_key:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client
    
    def is_available(self) -> bool:
        """检查AI评估是否可用"""
        return self.enabled and HAS_OPENAI and bool(self.api_key) and self.client is not None
    
    def evaluate(self, content: str, ext: str) -> QualityResult:
        """评估字幕质量"""
        if not self.is_available():
            return QualityResult(
                available=False,
                fluency=0,
                accuracy=0,
                localization=0,
                professionalism=0,
                overall_score=0,
                is_machine_translation=False,
                confidence=0,
                issues=[],
                summary="AI评估未启用或不可用",
                error="AI评估未启用或不可用"
            )
        
        text = extract_text(content, ext)
        
        if not text or len(text) < 10:
            return QualityResult(
                available=False,
                fluency=0,
                accuracy=0,
                localization=0,
                professionalism=0,
                overall_score=0,
                is_machine_translation=False,
                confidence=0,
                issues=[],
                summary="文本内容太少",
                error="文本内容太少"
            )
        
        invalid_patterns = [
            r'第一会所',
            r'sis001\.com',
            r'BT压片组',
            r'getsisurl@gmail\.com',
            r'云的守望',
            r'压制组',
            r'字幕组.*广告',
            r'www\.[a-z0-9]+\.com',
        ]
        
        invalid_count = 0
        for pattern in invalid_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                invalid_count += 1
        
        text_lines = [line.strip() for line in text.split('\n') if line.strip()]
        unique_lines = set(text_lines)
        
        if invalid_count >= 2 or len(unique_lines) <= 5:
            return QualityResult(
                available=False,
                fluency=0,
                accuracy=0,
                localization=0,
                professionalism=0,
                overall_score=0,
                is_machine_translation=False,
                confidence=0,
                issues=["无效字幕", "仅包含广告水印"],
                summary="无效字幕：仅包含广告水印，无实际内容",
                error="无效字幕"
            )
        
        try:
            start_time = time.time()
            
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

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的字幕翻译质量评估专家。请客观评估字幕质量，识别机器翻译痕迹。只返回JSON格式的结果。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            elapsed_time = time.time() - start_time
            
            response_content = response.choices[0].message.content
            
            json_match = re.search(r'\{[\s\S]*\}', response_content)
            if json_match:
                data = json.loads(json_match.group())
                return QualityResult(
                    available=True,
                    fluency=float(data.get('fluency', 0)),
                    accuracy=float(data.get('accuracy', 0)),
                    localization=float(data.get('localization', 0)),
                    professionalism=float(data.get('professionalism', 0)),
                    overall_score=float(data.get('overall_score', 0)),
                    is_machine_translation=bool(data.get('is_machine_translation', False)),
                    confidence=float(data.get('confidence', 0)),
                    issues=data.get('issues', []),
                    summary=data.get('summary', ''),
                    elapsed_time=elapsed_time
                )
            else:
                return QualityResult(
                    available=False,
                    fluency=0,
                    accuracy=0,
                    localization=0,
                    professionalism=0,
                    overall_score=0,
                    is_machine_translation=False,
                    confidence=0,
                    issues=[],
                    summary="无法解析AI响应",
                    error="无法解析AI响应",
                    elapsed_time=elapsed_time
                )
                
        except Exception as e:
            return QualityResult(
                available=False,
                fluency=0,
                accuracy=0,
                localization=0,
                professionalism=0,
                overall_score=0,
                is_machine_translation=False,
                confidence=0,
                issues=[],
                summary=f"评估失败: {str(e)}",
                error=str(e)
            )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "enabled": self.enabled,
            "available": self.is_available(),
            "api_key_set": bool(self.api_key),
            "base_url": self.base_url,
            "model": self.model
        }


class RuleBasedEvaluator:
    """基于规则的评估器（无需API）"""
    
    def is_available(self) -> bool:
        """检查评估器是否可用"""
        return True
    
    def evaluate(self, content: str, ext: str) -> QualityResult:
        """基于规则评估字幕质量"""
        text = extract_text(content, ext)
        
        if not text or len(text) < 10:
            return QualityResult(
                available=False,
                fluency=0,
                accuracy=0,
                localization=0,
                professionalism=0,
                overall_score=0,
                is_machine_translation=False,
                confidence=0,
                issues=["文本内容太少"],
                summary="文本内容太少"
            )
        
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
        
        return QualityResult(
            available=True,
            fluency=scores["fluency"],
            accuracy=scores["accuracy"],
            localization=scores["localization"],
            professionalism=scores["professionalism"],
            overall_score=overall,
            is_machine_translation=is_mt,
            confidence=0.6,
            issues=issues,
            summary="基于规则评估" + ("，疑似机器翻译" if is_mt else "")
        )


def get_evaluator(config: dict) -> AIEvaluator | RuleBasedEvaluator:
    """根据配置获取评估器"""
    ai_config = config.get("ai_evaluator", {})
    
    if ai_config.get("enabled", False):
        return AIEvaluator(
            api_key=ai_config.get("api_key", ""),
            base_url=ai_config.get("base_url", "https://api.deepseek.com"),
            model=ai_config.get("model", "deepseek-chat"),
            enabled=True
        )
    else:
        return RuleBasedEvaluator()
