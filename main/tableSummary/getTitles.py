from openai import OpenAI
import os
import json
import re
import logging
import time
import yaml  # 新增导入

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

# 新增配置加载函数（放在其他导入之后）
def load_api_config(config_path="config.yaml"):
    """加载API配置"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return {
                "key": config['api']['key'],
                "base_url": config['api']['base_url']
            }
    except Exception as e:
        logging.error(f"配置加载失败: {str(e)}")
        raise RuntimeError("请检查config.yaml配置文件是否存在且格式正确")

def extract_json_from_response(response_text, target_field=None, logger=None):
    """
    从API响应中提取JSON数据，具有多层级回退策略
    
    Args:
        response_text (str): 原始响应文本
        target_field (str, optional): 需要提取的特定字段，不指定则返回整个JSON
        logger (logging.Logger, optional): 日志记录器
    
    Returns:
        dict/str: 提取的JSON数据或指定字段值
    
    Raises:
        ValueError: 当所有提取方法都失败时抛出
    """
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    
    logger.debug("开始从响应中提取JSON")
    
    # 策略1: 尝试提取```json和```之间的内容
    try:
        # 处理可能存在的多种代码块格式
        json_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        matches = re.findall(json_pattern, response_text)
        
        if matches:
            for match in matches:
                try:
                    json_str = match.strip()
                    content_json = json.loads(json_str)
                    logger.debug("成功从代码块中提取JSON字符串")
                    return content_json[target_field] if target_field else content_json
                except:
                    continue
    except Exception as e:
        logger.warning(f"从代码块提取JSON失败: {str(e)}")
    
    # 策略2: 尝试直接解析整个响应
    try:
        content_json = json.loads(response_text)
        logger.debug("成功解析整个响应为JSON")
        return content_json[target_field] if target_field else content_json
    except Exception as e:
        logger.warning(f"直接解析响应为JSON失败: {str(e)}")
    
    # 策略3: 尝试查找和提取JSON对象
    try:
        pattern = r'{[\s\S]*}'
        match = re.search(pattern, response_text)
        if match:
            json_str = match.group(0)
            content_json = json.loads(json_str)
            logger.debug("通过正则表达式提取JSON对象成功")
            return content_json[target_field] if target_field else content_json
    except Exception as e:
        logger.warning(f"通过正则表达式提取JSON对象失败: {str(e)}")
    
    # 策略4: 如果指定了目标字段，尝试直接提取该字段
    if target_field:
        try:
            # 尝试匹配 "field": "value" 或 "field":"value" 模式
            pattern = f'"{target_field}"\\s*:\\s*"([^"]*)"'
            match = re.search(pattern, response_text)
            if match:
                extracted_value = match.group(1)
                logger.debug(f"通过正则表达式成功提取 {target_field} 字段")
                return extracted_value
                
            # 尝试匹配 "field": 数值 模式
            pattern = f'"{target_field}"\\s*:\\s*([0-9.]+)'
            match = re.search(pattern, response_text)
            if match:
                extracted_value = match.group(1)
                try:
                    # 尝试转换为数值
                    if '.' in extracted_value:
                        return float(extracted_value)
                    else:
                        return int(extracted_value)
                except:
                    return extracted_value
        except Exception as e:
            logger.warning(f"通过正则表达式提取字段失败: {str(e)}")
    
    # 记录详细的错误信息
    logger.error("所有JSON提取方法均失败")
    logger.error(f"原始响应: {response_text[:100]}...")
    
    raise ValueError(f"无法从响应中提取有效的JSON数据或{target_field}字段")

def generate_table_summary(json_file_path, api_key=None, base_url=None):
    """
    从JSON文件生成表格摘要
    
    Args:
        json_file_path (str): JSON文件路径
        api_key (str, optional): Qwen API密钥
        base_url (str, optional): Qwen API基础URL
    
    Returns:
        list: 包含所有表格摘要的列表
    """
    # 加载配置
    try:
        config = load_api_config()
        # 优先使用传入参数，其次使用配置文件
        final_api_key = api_key or config['key']
        final_base_url = base_url or config['base_url']
    except Exception as e:
        logger.error("API配置加载失败，请检查config.yaml文件")
        raise

    # 初始化OpenAI客户端
    client = OpenAI(
        api_key=final_api_key,
        base_url=final_base_url
    )
    
    logger.info(f"开始处理JSON文件: {json_file_path}")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            tables_data = json.load(file)
        
        # 过滤出有效表格并记录原始索引
        valid_tables = [(idx, t) for idx, t in enumerate(tables_data) if t['type'] == 'table']
        if not valid_tables:
            logger.warning("未找到有效表格数据")
            return []

        # 更新prompt要求
        batch_prompt = f"""
        请为以下{len(valid_tables)}个财务表格生成唯一标题，严格按照JSON格式返回：
        {{
          "titles": {{
            "0": "表格1标题",
            "1": "表格2标题"
          }}
        }}

        标题要求：
        1. 10-20个连续中文字符（不要使用空格或符号分隔）
        2. 包含关键财务指标（如合并损益表/资产负债表等）
        3. 体现时间范围（2024年度/2023-2024等） 
        4. 业务板块信息（如有：方便面/饮料/其他业务）

        表格数据列表：
        {json.dumps([t[1] for t in valid_tables], ensure_ascii=False, indent=2)}
        """

        # 单次API调用
        response = client.chat.completions.create(
            model="deepseek-v3",
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "你是财务报告智能处理系统，生成紧凑无空格的中文标题"},
                {"role": "user", "content": batch_prompt}
            ],
        )
        response_content = response.choices[0].message.content

        # 解析批量结果
        try:
            batch_result = json.loads(response_content)
            titles_mapping = batch_result.get("titles", {})
            
            for orig_idx, (table_idx, table) in enumerate(valid_tables):
                title = titles_mapping.get(str(orig_idx), "标题生成失败")
                # 清洗逻辑（保持原有优化）
                clean_title = (
                    title.strip()
                    .replace(" ", "")    # 去除所有空格
                    .replace("；", "")   # 去除中文分号
                    .replace("\u3000", "")  # 去除全角空格
                    .replace("\n", "")  # 去除换行符
                )
                # 使用英文点号作为序号分隔符
                tables_data[table_idx]["title"] = f"{orig_idx+1}.{clean_title}"
            
            return tables_data

        except Exception as e:
            logger.error(f"批量标题解析失败: {str(e)}")
            return tables_data

    except Exception as e:
        logger.error(f"处理JSON文件失败: {str(e)}")
        raise

# 更新主函数
if __name__ == "__main__":
    # 设置输入输出路径
    input_json_path = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_origin_tables.json"
    output_json_path = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_table_titles.json"
    
    logger.info("表格摘要生成工具启动")
    
    try:
        # 生成摘要
        start_time = time.time()
        summaries = generate_table_summary(input_json_path)
        
        # 保存结果
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump({"tables": summaries}, f, ensure_ascii=False, indent=2)
            
        # 统计信息
        success_count = len([s for s in summaries if "error" not in s])
        total_tables = len(summaries)
        time_used = time.time() - start_time
        
        logger.info(f"处理完成！成功处理 {success_count}/{total_tables} 个表格")
        logger.info(f"平均处理速度：{time_used/total_tables:.2f}秒/表格")
        logger.info(f"结果文件已保存至：{output_json_path}")
        
    except Exception as e:
        logger.exception(f"主流程执行失败: {e}")
