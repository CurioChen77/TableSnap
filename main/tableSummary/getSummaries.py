from openai import OpenAI
import os
import json
import re
import logging
import time
from tqdm import tqdm
import yaml  # 新增导入

# 设置日志
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

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

# 新增配置加载函数
def load_config(config_path="config.yaml"):
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('api', {})
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        return {}

def generate_table_summary(json_file_path):
    # 加载配置
    api_config = load_config()
    
    client = OpenAI(
        api_key=api_config.get("key"),  # 从配置获取
        base_url=api_config.get("base_url")  # 从配置获取
    )
    
    logger.info(f"开始处理JSON文件: {json_file_path}")
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            # 修正点：获取tables数组
            data = json.load(file)
            tables_data = data.get("tables", [])  # 从根对象获取tables数组
        
        valid_tables = [(idx, t) for idx, t in enumerate(tables_data) if t['type'] == 'table']
        
        # 新增分析prompt模板
        analysis_prompt_template = """
        请分析以下财务表格，生成包含以下要素的100-200字摘要：
        1. 表格主要内容（损益/资产负债/现金流等）
        2. 关键数据指标（收入/利润/增长率等） 
        3. 时间范围对比（如有）
        4. 业务板块表现（如有）
        5. 重要财务比率（如有）
        
        要求：
        - 使用专业财务术语但保持简洁
        - 突出关键数据变化
        - 避免重复表格标题内容
        
        表格数据：
        {table_data}
        
        请返回JSON格式：
        {{
            "summary": "该表展示......" 
        }}
        """

        # 新增进度条
        progress_bar = tqdm(
            valid_tables, 
            desc="分析表格进度", 
            unit="table",
            dynamic_ncols=True
        )

        for table_idx, table in progress_bar:
            try:
                # 更新进度条描述
                progress_bar.set_postfix({"当前表格": f"{table_idx+1}/{len(valid_tables)}"})
                
                # 单个表格分析
                response = client.chat.completions.create(
                    model="qwen-plus",
                    temperature=0.2,  # 适当提高创造性
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "你是财务分析师，擅长提炼表格核心信息"},
                        {"role": "user", "content": analysis_prompt_template.format(
                            table_data=json.dumps(table, ensure_ascii=False)
                        )}
                    ],
                )
                analysis_result = json.loads(response.choices[0].message.content)
                
                # 新增summary字段
                tables_data[table_idx]["summary"] = analysis_result.get("summary", "分析生成失败")

            except Exception as e:
                logger.error(f"表格{table_idx}分析失败: {str(e)}")
                tables_data[table_idx]["summary"] = "分析生成失败"
        
        return tables_data

    except Exception as e:
        logger.error(f"处理JSON文件失败: {str(e)}")
        raise

# 更新主函数
if __name__ == "__main__":
    # 设置输入输出路径
    input_json_path = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_table_titles.json"
    output_json_path = "/home/curio/workspace/python-projects/TableSnap/output/20250425_183046_73b4d7c7/康师傅2024_table_summaries.json"
    
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
