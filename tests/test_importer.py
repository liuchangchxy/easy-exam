#!/usr/bin/env python3
"""Unit tests for Bank Ingestion Pipeline: Text/Markdown, CSV, and JSON parsers."""
import json
import unittest

from backend.services.importer import (
    TextExamParser,
    CsvExamParser,
    JsonExamParser,
    ExcelExamParser,
    parse_markdown_text,
    parse_csv_content,
    parse_json_content,
    parse_excel_content,
)


class TestTextExamParser(unittest.TestCase):
    """Test Text/Markdown regex state machine question parser."""

    def test_single_choice_parsing(self):
        """Verify standard single choice question extraction."""
        content = """
1. 刑法中关于正当防卫的规定，下列说法正确的是？
A. 必须针对不法侵害人本人实行
B. 可以针对不法侵害人的亲友实行
C. 防卫过当不负刑事责任
D. 事后防卫也属于正当防卫
【答案】A
【解析】正当防卫只能针对不法侵害人本人，防卫过当负刑事责任，事后防卫不是正当防卫。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q["stem"], "刑法中关于正当防卫的规定，下列说法正确的是？")
        self.assertEqual(q["type"], "SINGLE")
        self.assertEqual(q["answer"], "A")
        self.assertEqual(len(q["options"]), 4)
        self.assertEqual(q["options"][0], {"key": "A", "content": "必须针对不法侵害人本人实行"})
        self.assertEqual(q["options"][1], {"key": "B", "content": "可以针对不法侵害人的亲友实行"})
        self.assertEqual(q["options"][2], {"key": "C", "content": "防卫过当不负刑事责任"})
        self.assertEqual(q["options"][3], {"key": "D", "content": "事后防卫也属于正当防卫"})
        self.assertIn("正当防卫只能针对不法侵害人本人", q["explanation"])
        self.assertEqual(q["difficulty"], 3)
        self.assertIsInstance(q["tags"], list)

    def test_multiple_choice_parsing(self):
        """Verify multiple choice question extraction and type auto-inference."""
        content = """
2、下列属于我国刑法规定的附加刑的有？
A. 罚金
B. 剥夺政治权利
C. 没收财产
D. 拘役
答案：ABC
解析：拘役属于刑罚主刑，罚金、剥夺政治权利、没收财产属于附加刑。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q["type"], "MULTI")
        self.assertEqual(q["answer"], "ABC")
        self.assertEqual(len(q["options"]), 4)
        self.assertIn("拘役属于刑罚主刑", q["explanation"])

    def test_judge_question_parsing(self):
        """Verify judge / true-false question extraction and type auto-inference."""
        content = """
(1) 中华人民共和国的一切权力属于人民。
【答案】正确
【解析】《宪法》第二条规定，中华人民共和国的一切权力属于人民。

【2】 驾驶机动车在高速公路上倒车一次记6分。
A. 对
B. 错
答案：错
解析：高速公路上倒车一次记12分。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 2)

        q1 = questions[0]
        self.assertEqual(q1["stem"], "中华人民共和国的一切权力属于人民。")
        self.assertEqual(q1["type"], "JUDGE")
        self.assertIn(q1["answer"], ("T", "正确"))
        self.assertIn("《宪法》第二条", q1["explanation"])

        q2 = questions[1]
        self.assertEqual(q2["stem"], "驾驶机动车在高速公路上倒车一次记6分。")
        self.assertEqual(q2["type"], "JUDGE")
        self.assertIn(q2["answer"], ("F", "错", "B"))
        self.assertEqual(len(q2["options"]), 2)

    def test_essay_question_parsing(self):
        """Verify essay / text answer extraction when no options exist."""
        content = """
1. 请简述面向对象编程的三大基本特征。
【答案】封装、继承、多态。
【解析】三大基本特征是面向对象语言的核心基础。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(q["type"], "ESSAY")
        self.assertEqual(len(q["options"]), 0)
        self.assertIn("封装、继承、多态", q["answer"])
        self.assertIn("核心基础", q["explanation"])

    def test_multiline_stem_and_explanation(self):
        """Verify multiline stems with code and multiline explanation paragraphs."""
        content = """
1. 观察以下 Python 代码片段：
```python
def calc(x):
    return x * 2 + 1
print(calc(3))
```
请问上述程序的终端输出结果是？
A. 6
B. 7
C. 8
D. 9
【答案】B
【解析】本题考查基础 Python 函数调用与算术运算。
首先传入参数 x = 3。
执行 3 * 2 + 1 得到 7。
因此 print 输出为 7。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertIn("def calc(x):", q["stem"])
        self.assertIn("print(calc(3))", q["stem"])
        self.assertIn("请问上述程序的终端输出结果是？", q["stem"])
        self.assertEqual(q["answer"], "B")
        self.assertEqual(len(q["options"]), 4)
        self.assertIn("首先传入参数 x = 3。", q["explanation"])
        self.assertIn("因此 print 输出为 7。", q["explanation"])

    def test_single_line_multiple_options(self):
        """Verify parsing options placed on a single line."""
        content = """
1. 下列哪个是 Python 的内置数据类型？
A. list   B. Array   C. Vector   D. LinkedList
【答案】A
【解析】list 是 Python 原生内置类型。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        q = questions[0]
        self.assertEqual(len(q["options"]), 4)
        self.assertEqual(q["options"][0]["content"], "list")
        self.assertEqual(q["options"][1]["content"], "Array")
        self.assertEqual(q["options"][2]["content"], "Vector")
        self.assertEqual(q["options"][3]["content"], "LinkedList")

    def test_various_prefixes_and_indicators(self):
        """Verify support for diverse numbering styles and indicators."""
        content = """
1. 第一题
(A) 选项A
（B） 选项B
[C] 选项C
【D】 选项D
【正解】A
【分析】第一题分析

2 第二题
A、甲
B、乙
C、丙
D、丁
Answer: B
Explanation: 第二题解析

第3题: 第三题
A. 1
B. 2
参考答案： A
答案解析： 第三题解析
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 3)
        self.assertEqual(questions[0]["answer"], "A")
        self.assertEqual(questions[1]["answer"], "B")
        self.assertEqual(questions[2]["answer"], "A")
        self.assertEqual(len(questions[0]["options"]), 4)
        self.assertEqual(len(questions[1]["options"]), 4)
        self.assertEqual(len(questions[2]["options"]), 2)

    def test_text_difficulty_and_tags(self):
        """Verify parsing difficulty and tag indicators in text format."""
        content = """
1. 刑法第三条规定了罪刑法定原则。
A. 正确
B. 错误
【答案】A
【难度】4
【标签】刑法, 罪刑法定, 总则
【解析】我国刑法明确规定了罪刑法定原则。
"""
        questions = TextExamParser.parse(content)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["difficulty"], 4)
        self.assertEqual(questions[0]["tags"], ["刑法", "罪刑法定", "总则"])

    def test_functional_helper(self):
        """Verify parse_markdown_text functional alias."""
        text = "1. 测试题目\nA. 1\nB. 2\n【答案】A\n【解析】无"
        res = parse_markdown_text(text)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["answer"], "A")



class TestCsvExamParser(unittest.TestCase):
    """Test CSV question parser with flexible Chinese column mapping."""

    def test_standard_chinese_headers(self):
        """Verify CSV parsing with standard Chinese column names."""
        csv_data = """题干,选项A,选项B,选项C,选项D,答案,解析
我国现行宪法是哪一年颁布的？,1954年,1975年,1978年,1982年,D,现行宪法为1982年宪法
下列哪些属于行政处罚的种类？,警告,罚款,行政拘留,有期徒刑,ABC,有期徒刑属于刑罚
"""
        questions = CsvExamParser.parse(csv_data)
        self.assertEqual(len(questions), 2)

        q1 = questions[0]
        self.assertEqual(q1["stem"], "我国现行宪法是哪一年颁布的？")
        self.assertEqual(q1["type"], "SINGLE")
        self.assertEqual(q1["answer"], "D")
        self.assertEqual(len(q1["options"]), 4)
        self.assertEqual(q1["options"][3]["content"], "1982年")
        self.assertIn("1982年宪法", q1["explanation"])

        q2 = questions[1]
        self.assertEqual(q2["stem"], "下列哪些属于行政处罚的种类？")
        self.assertEqual(q2["type"], "MULTI")
        self.assertEqual(q2["answer"], "ABC")
        self.assertEqual(len(q2["options"]), 4)

    def test_flexible_column_aliases_and_bom(self):
        """Verify CSV parsing with alternative column aliases and utf-8-sig BOM."""
        csv_data = "\ufeff题目,A,B,C,D,正解,分析,题型,难度\n" \
                   "地球是不是圆的？,是,不是,,,A,科学事实,判断题,1\n" \
                   "Python是一门编译型语言吗？,对,错,,,B,Python是解释型语言,判断,2\n"

        questions = CsvExamParser.parse(csv_data)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["type"], "JUDGE")
        self.assertEqual(questions[0]["difficulty"], 1)
        self.assertEqual(questions[1]["type"], "JUDGE")
        self.assertEqual(questions[1]["difficulty"], 2)

    def test_csv_gbk_bytes(self):
        """Verify CSV decoding with GBK encoded bytes."""
        csv_text = "题干,A,B,答案\n中国的首都是哪里？,北京,上海,A\n"
        gbk_bytes = csv_text.encode("gbk")
        questions = CsvExamParser.parse(gbk_bytes)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["stem"], "中国的首都是哪里？")
        self.assertEqual(questions[0]["answer"], "A")

    def test_csv_functional_helper(self):
        """Verify parse_csv_content functional alias."""
        csv_data = "stem,A,B,answer\n1+1=?,1,2,B\n"
        questions = parse_csv_content(csv_data)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["answer"], "B")

    def test_empty_inputs(self):
        """Verify empty inputs return empty lists."""
        self.assertEqual(TextExamParser.parse(""), [])
        self.assertEqual(CsvExamParser.parse(""), [])
        self.assertEqual(JsonExamParser.parse(""), [])



class TestJsonExamParser(unittest.TestCase):
    """Test JSON question parser with schema validation."""

    def test_valid_json_list_parsing(self):
        """Verify parsing valid list of questions in JSON format."""
        data = [
            {
                "stem": "关于常染色体显性遗传，下列说法正确的是？",
                "type": "SINGLE",
                "options": [
                    {"key": "A", "content": "男女发病概率相等"},
                    {"key": "B", "content": "患者双亲必有一方患病"},
                ],
                "answer": "A",
                "explanation": "常染色体显性遗传男女发病率相等。",
                "difficulty": 4,
                "tags": ["遗传学", "生物"]
            }
        ]
        questions = JsonExamParser.parse(json.dumps(data, ensure_ascii=False))
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["stem"], data[0]["stem"])
        self.assertEqual(questions[0]["type"], "SINGLE")
        self.assertEqual(questions[0]["difficulty"], 4)
        self.assertEqual(questions[0]["tags"], ["遗传学", "生物"])

    def test_json_wrapped_dict_parsing(self):
        """Verify parsing JSON with top-level 'questions' or 'data' key."""
        payload = {
            "bank_name": "测试题库",
            "questions": [
                {
                    "stem": "简答题：什么是死锁？",
                    "answer": "死锁是指两个或两个以上进程互相等待对方持有的资源而停滞不前。",
                    "explanation": "死锁产生的四个必要条件：互斥、占有且等待、不可抢占、循环等待。"
                }
            ]
        }
        questions = JsonExamParser.parse(json.dumps(payload, ensure_ascii=False))
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["type"], "ESSAY")
        self.assertEqual(questions[0]["options"], [])

    def test_json_validation_errors(self):
        """Verify invalid JSON raises ValueError with informative messages."""
        # Bad syntax
        with self.assertRaises(ValueError):
            JsonExamParser.parse("{ invalid json")

        # Missing required stem
        with self.assertRaises(ValueError):
            JsonExamParser.parse(json.dumps([{"answer": "A"}]))

        # Non list / non dict structure
        with self.assertRaises(ValueError):
            JsonExamParser.parse(json.dumps("just a string"))

    def test_json_functional_helper(self):
        """Verify parse_json_content functional alias."""
        payload = [{"stem": "2+2=?", "options": [{"key": "A", "content": "4"}], "answer": "A"}]
        res = parse_json_content(json.dumps(payload))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["answer"], "A")


class TestExcelExamParser(unittest.TestCase):
    """Test Excel (.xlsx) file ingestion and column mapping."""

    def test_excel_parsing_with_openpyxl(self):
        """Verify creating an Excel workbook in-memory and parsing it correctly."""
        import io
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "题库"

        # Headers
        ws.append([
            "题干", "题型", "选项A", "选项B", "选项C", "选项D",
            "正确答案", "解析", "难度", "标签"
        ])

        # Single choice question
        ws.append([
            "Python 中哪个关键字用于定义函数？",
            "单选",
            "def",
            "func",
            "function",
            "define",
            "A",
            "Python 使用 def 关键字定义函数。",
            "2",
            "Python, 基础语法"
        ])

        # Multi choice question
        ws.append([
            "下列哪些是 Python 的可变数据类型？",
            "多选题",
            "列表 (list)",
            "字典 (dict)",
            "元组 (tuple)",
            "集合 (set)",
            "ABD",
            "列表、字典、集合是可变类型，元组是不可变类型。",
            "3",
            "Python, 数据结构"
        ])

        # Judge question
        ws.append([
            "Python 中的字符串是可变对象。",
            "判断题",
            "",
            "",
            "",
            "",
            "错误",
            "Python 字符串是不可变对象。",
            "2",
            "Python, 字符串"
        ])

        bio = io.BytesIO()
        wb.save(bio)
        wb.close()
        bio.seek(0)

        questions = parse_excel_content(bio.getvalue())
        self.assertEqual(len(questions), 3)

        # Question 1: Single choice
        q1 = questions[0]
        self.assertEqual(q1["stem"], "Python 中哪个关键字用于定义函数？")
        self.assertEqual(q1["type"], "SINGLE")
        self.assertEqual(q1["answer"], "A")
        self.assertEqual(len(q1["options"]), 4)
        self.assertEqual(q1["options"][0]["content"], "def")
        self.assertEqual(q1["difficulty"], 2)
        self.assertIn("基础语法", q1["tags"])

        # Question 2: Multi choice
        q2 = questions[1]
        self.assertEqual(q2["stem"], "下列哪些是 Python 的可变数据类型？")
        self.assertEqual(q2["type"], "MULTI")
        self.assertEqual(q2["answer"], "ABD")
        self.assertEqual(len(q2["options"]), 4)

        # Question 3: Judge
        q3 = questions[2]
        self.assertEqual(q3["stem"], "Python 中的字符串是可变对象。")
        self.assertEqual(q3["type"], "JUDGE")
        self.assertEqual(q3["answer"], "F")
        self.assertEqual(len(q3["options"]), 0)

    def test_excel_empty_handling(self):
        """Verify empty workbook returns empty list."""
        import io
        import openpyxl

        wb = openpyxl.Workbook()
        bio = io.BytesIO()
        wb.save(bio)
        wb.close()
        bio.seek(0)

        questions = parse_excel_content(bio.getvalue())
        self.assertEqual(questions, [])


if __name__ == "__main__":
    unittest.main()
