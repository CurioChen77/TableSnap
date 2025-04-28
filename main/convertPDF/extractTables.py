import json
import os

# 定义输入和输出路径
input_json_path = '/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_content_list.json'

# 提取原名称并生成新的输出文件名
base_name = os.path.basename(input_json_path)  # 获取文件名
name_without_extension = os.path.splitext(base_name)[0]  # 去掉扩展名
output_json_path = os.path.join(
    os.path.dirname(input_json_path),  # 获取文件所在目录
    f"{name_without_extension.split('_content_list')[0]}_origin_tables.json"  # 生成新文件名
)

# 读取输入JSON文件
with open(input_json_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

# 提取所有表格数据
tables = [item for item in data if item['type'] == 'table']

# 将提取的表格数据保存到新的JSON文件
with open(output_json_path, 'w', encoding='utf-8') as file:
    json.dump(tables, file, ensure_ascii=False, indent=4)

print(f"表格数据已成功提取并保存到 {output_json_path}")
