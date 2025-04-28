import json
import re

def json_to_markdown(input_path, output_path):
    """
    将JSON表格数据转换为Markdown格式
    
    Args:
        input_path (str): 输入JSON文件路径
        output_path (str): 输出Markdown文件路径
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    md_content = []
    
    for table in data.get("tables", []):
        # 标题
        md_content.append(f"# {table.get('title', '')}\n")
        
        # 总结
        if summary := table.get("summary"):
            md_content.append("## 表格总结\n")
            md_content.append(f"{summary}\n\n")
        
        # 表格内容
        md_content.append("## 表格内容\n")
        
        # 表格标题
        if captions := table.get("table_caption"):
            md_content.append(f"**表格标题：{captions[0].strip()}**\n\n")
        
        # 处理表格主体
        table_body = table.get("table_body", "")
        cleaned_table = re.sub(r'</?html>|</?body>', '', table_body).strip()
        md_content.append(f"{cleaned_table}\n\n")
        
        # 脚注
        if footnotes := table.get("table_footnote"):
            md_content.append(f"**表格脚注：{footnotes[0].strip()}**\n\n")
        
        # 附加信息
        img_path = table.get('img_path', '')
        if img_path:
            md_content.append(f"![表格截图]({img_path})\n\n")
        
        md_content.append(f"### *页码: {table.get('page_idx', 0) + 1}*\n\n")
        md_content.append("---\n\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(md_content)

if __name__ == "__main__":
    input_json = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_table_summaries.json"
    output_md = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_表格.md"
    json_to_markdown(input_json, output_md)
