#!/usr/bin/env python3
"""
ASR 转录文本清理脚本
=====================
清理 Vosk 中文转录输出：去除逐词空格、修正常见ASR错误、段落分段。

用法：
    python cleanup_transcript.py --input <原始转录文件> --output <清理后文件>

示例：
    python cleanup_transcript.py --input transcript.txt --output transcript_clean.txt
"""
import argparse
import os
import re
import sys


def remove_cn_spaces(text: str) -> str:
    """去除中文字符之间的空格（Vosk中文输出特征：每个词之间都有空格）"""
    result = []
    for i, ch in enumerate(text):
        if ch == " ":
            prev_ch = text[i - 1] if i > 0 else ""
            next_ch = text[i + 1] if i + 1 < len(text) else ""

            def is_cjk(c):
                return "\u4e00" <= c <= "\u9fff" or c in "，。、！？；：""''（）【】《》—…"

            if is_cjk(prev_ch) and is_cjk(next_ch):
                continue  # Skip space between Chinese characters
        result.append(ch)
    return "".join(result)


def remove_all_cn_spaces(text: str) -> str:
    """激进模式：去除所有空格（适用于纯中文文本）"""
    return re.sub(r"\s+", "", text)


# 常见 ASR 错误修正表
# 格式：(错误文本, 正确文本)
# 注意：替换顺序很重要，长文本优先
ASR_FIXES = [
    # === 核心术语修正 ===
    ("美原", "美元"),
    ("直逼的贬值", "纸币的贬值"),
    ("直逼的谎言", "纸币的谎言"),
    ("直逼", "纸币"),
    ("通过膨胀", "通货膨胀"),
    ("通过紧缩", "通货紧缩"),
    ("天感染", "天然"),
    ("五上线", "无上限"),
    ("彼岸", "必然"),
    ("经济激起", "经济机器"),
    ("激起是", "机器是"),

    # === 金融/经济术语 ===
    ("之出", "支出"),
    ("总之出", "总支出"),
    ("做之初", "做支出"),
    ("紧锁", "紧缩"),
    ("兜销", "核销"),
    ("和战争", "核战争"),
    ("之县级", "现金"),
    ("碧玺", "必须"),
    ("鲍蕾", "暴雷"),
    ("保留的挤兑", "暴雷的挤兑"),
    ("保留", "暴雷"),  # 在金融上下文中
    ("挤兑朝", "挤兑潮"),
    ("股排", "骨牌"),
    ("超发", "超发"),  # 正确，保留

    # === 常见同音错字 ===
    ("首个", "收割"),
    ("人挣的", "真正的"),
    ("首个", "收割"),
    ("之五百万", "值五百万"),
    ("盾构", "断供"),
    ("事业和", "失业和"),
    ("事业", "失业"),  # 在经济上下文中
    ("爹的比", "跌得比"),
    ("贴明天", "跌明天"),
    ("今天贴", "今天跌"),
    ("长不", "涨不"),
    ("明天长", "明天涨"),
    ("将不降息", "降不降息"),
    ("将其中", "降息"),
    ("假戏", "加息"),
    ("前了不", "钱了不"),

    # === 人名/专有名词 ===
    ("可能我卧室", "鲍威尔"),
    ("达里奥", "达里奥"),  # 正确
    ("桥水基金", "桥水基金"),  # 正确
    ("尼克松冲击", "尼克松冲击"),  # 正确
    ("凯恩斯", "凯恩斯"),  # 正确
    ("布雷顿森林", "布雷顿森林"),  # 正确

    # === 动作/状态词 ===
    ("介意做事", "节衣缩食"),
    ("谈它", "坍塌"),
    ("线路", "陷入"),  # 在"陷入恶性循环"上下文
    ("正统", "紧缩"),  # 在"紧缩"上下文
    ("整整晴空", "真正清空"),
    ("体谅", "体量"),  # 在"债务体量"上下文
    ("西安", "心安"),  # 在"让人心安"上下文
    ("难度", "懒惰"),  # 在"认知上的懒惰"上下文
    ("传下去", "转下去"),

    # === 数量/单位 ===
    ("酒钱会", "九千块"),
    ("九千会", "九千块"),
    ("领悟会", "零五块"),
    ("一百领悟会", "一百零五块"),
    ("几十万一", "几十万亿"),
    ("百分之三百上", "百分之三百以上"),

    # === 动词/副词 ===
    ("应姿态", "鹰派姿态"),
    ("应酬和", "印钞和"),
    ("大规模英超", "大规模印钞"),
    ("英超用", "印钞用"),
    ("大英超", "大印钞"),
    ("英超游戏", "印钞游戏"),
    ("英超", "印钞"),
    ("贫困有了", "央行印了"),
    ("反应涌入", "钞票涌入"),
    ("李大宝", "一大批"),
    ("深远", "深渊"),  # 在"万劫不复深渊"上下文
    ("食物的", "实物的"),
    ("食物上", "实物上"),
    ("先进的", "现金的"),
    ("先进的人", "现金的人"),
    ("先进", "现金"),  # 残余
    ("姐我", "解药"),
    ("留校", "流向"),
    ("许明", "续命"),
    ("出马", "借口"),  # 在"找借口"上下文
    ("冯路", "愤怒"),
    ("反整张图着", "掀整个桌子"),
    ("肯定效应", "坎蒂隆效应"),
    ("全程", "圈层"),  # 在"核心圈层"上下文
    ("喜事", "洗劫"),
    ("假期", "假象"),
    ("瞧瞧", "悄悄"),
    ("选项", "转移"),
    ("搞定", "高地"),  # 在"财富高地"上下文
    ("防御犬", "防御权"),
    ("精神鼓动", "精神股东"),
    ("福利赶车", "护城河"),
    ("应财富", "硬财富"),
    ("中战甲", "重战甲"),
    ("此时绑定", "深度绑定"),
    ("全球通", "全球公认的"),

    # === 其他 ===
    ("货币货币化", "债务货币化"),
    ("了宽松", "了量化宽松"),
    ("只是避免多", "只是凭空多"),
    ("一幅名义", "政府名义"),
    ("一百一现金", "一百亿现金"),
    ("围着小时", "为这实质"),
    ("香相信", "相信"),
    ("微博利息", "微薄利息"),
    ("藏的银行", "存的银行"),
    ("进屋史", "金融史"),
    ("历史碰见", "历史瞬间"),
    ("之猫", "之锚"),
    ("黄金只猫", "黄金之锚"),
    ("同过借贷", "通过借贷"),
    ("同过", "通过"),
    ("性感债务", "新增债务"),
    ("怎么讲法律", "怎么涨法币"),
    ("法律的数量", "法币的数量"),
    ("之选", "只算"),
    ("一抹和", "一而足"),
    ("打开新看到", "打开新闻看到"),
    ("打开新", "打开新闻"),
    ("有在激烈", "又在激烈"),
    ("美联储有在", "美联储又在"),
    ("不看牌除", "不排除"),
    ("不牌除", "不排除"),
    ("营养死纯金", "盎司纯金"),
    ("重视断开", "正式断开"),
    ("安全绳", "安全绳"),  # 正确
    ("慢点量", "慢变量"),
    ("文明慢变量", "文明慢变量"),  # 正确
    ("天感染", "天然"),
    ("一瓶的房子", "一平的房子"),
    ("一万块钱一瓶", "一万块钱一平"),
    ("之之一匹不", "织一匹布"),
    ("之一匹不", "织一匹布"),
    ("之几", "织几"),
    ("裨补", "匹布"),
    ("手工支部", "手工织布"),
    ("工具演技", "工具演进"),
    ("操作机体", "操作机器"),
    ("机体就是有", "机器就是由"),
    ("卖买房", "卖方"),
    ("卖房买房", "卖方"),
    ("买房付出", "买方付出"),
    ("三四店", "4S店"),
    ("原始说会", "原始社会"),
    ("一百倍可", "一百块可"),
    ("哎通过", "爱通过"),
    ("很有黄", "很慌"),
    ("打着官网网上找", "打着滚往上走"),
    ("打着官网", "打着滚"),
    ("这个越多多", "这个月多多"),
    ("物业体系", "法币体系"),
    ("现在物体系", "现代法币体系"),
    ("物体系", "法币体系"),
    ("现代物体系", "现代法币体系"),
    ("应排", "鹰牌"),  # 美联储鹰派
    ("硬派", "鹰派"),
    ("论文的", "牢牢的"),
    ("技术孩子", "技术还在"),
    ("只暴雷必要前", "只保留必要的钱"),
    ("这他有人类", "这台由人类"),
    ("干这一切", "但这一切"),
    ("你的在", "你的事"),
    ("购买力全球", "突破全球"),
    ("答案暗流", "那条暗流"),
    ("人物假象", "通胀像"),
    ("没多少年", "没多少人"),
]


def apply_fixes(text: str, custom_fixes: list = None) -> str:
    """应用ASR错误修正表"""
    fixes = ASR_FIXES + (custom_fixes or [])
    for old, new in fixes:
        text = text.replace(old, new)
    return text


def add_paragraphs(text: str, section_markers: list = None) -> str:
    """在关键内容转折处插入段落分隔"""
    if section_markers is None:
        section_markers = [
            "朋友们大家好",
            "我想请大家",
            "而我们今天",
            "绝大多数人",
            "要搞懂纸币",
            "第一个齿轮",
            "第二个齿轮",
            "第三个齿轮",
            "然而人类的",
            "借钱不是白送的",
            "这就是第二个",
            "每当这个时候",
            "如果每次经济",
            "终于我们迎来了",
            "第一张牌",
            "第二张牌",
            "第三张牌",
            "第四张牌",
            "现在牌桌上",
            "用一个最简单的",
            "你可能会问",
            "大错特错",
            "到底是谁为",
            "著名经济学家",
            "在1971年",
            "尼克松向",
            "当法币变成",
            "所以纸币贬值",
            "看到这里你觉得",
            "每当经济数据",
            "但如果站在",
            "美联储为什么",
            "但是能把刹车",
            "当实体经济",
            "在这样的大水",
            "基于前面",
            "原则一",
            "原则二",
            "原则三",
            "第一个就是",
            "第二个就是",
            "那好了我们",
        ]

    formatted = text
    for marker in section_markers:
        formatted = formatted.replace(marker, "\n\n" + marker)

    formatted = formatted.strip()
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    return formatted


def main():
    parser = argparse.ArgumentParser(description="Clean up Vosk ASR transcript")
    parser.add_argument("--input", required=True, help="Input transcript file")
    parser.add_argument("--output", required=True, help="Output cleaned file")
    parser.add_argument("--no-spaces", action="store_true",
                        help="Remove ALL spaces (aggressive mode for pure Chinese text)")
    parser.add_argument("--no-fixes", action="store_true",
                        help="Skip ASR error fixes (only remove spaces)")
    parser.add_argument("--no-paragraphs", action="store_true",
                        help="Skip paragraph insertion")
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    print(f"Input: {input_path} ({len(text)} chars)")

    # Step 1: Remove spaces
    if args.no_spaces:
        text = remove_all_cn_spaces(text)
    else:
        text = remove_cn_spaces(text)
    print(f"After space removal: {len(text)} chars")

    # Step 2: Apply ASR fixes
    if not args.no_fixes:
        text = apply_fixes(text)
        print(f"After ASR fixes: {len(text)} chars")

    # Step 3: Add paragraphs
    if not args.no_paragraphs:
        text = add_paragraphs(text)
        print(f"After paragraph insertion: {len(text)} chars")

    # Clean up any remaining whitespace issues
    text = re.sub(r"[ \t]+", "", text)  # Remove remaining spaces/tabs in Chinese text
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    # Save
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nOutput: {output_path} ({len(text)} chars)")

    # Preview
    print("\n" + "=" * 60)
    print("PREVIEW (first 1000 chars):")
    print("=" * 60)
    print(text[:1000])
    print("=" * 60)

    print(f"\nIMPORTANT: Auto-cleanup cannot fix all ASR errors.")
    print(f"Manual review required for: proper nouns, numbers, financial terms, and illogical sentences.")
    print(f"See references/asr_error_patterns.md for common error patterns.")


if __name__ == "__main__":
    main()
