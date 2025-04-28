import os
import sys
import uuid
import datetime
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import SupportedPdfParseMethod


def process_pdf(pdf_file_path):
    # 生成时间戳和UUID
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]

    # 创建输出目录
    output_base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Results")
    output_dir = os.path.join(output_base_dir, f"{timestamp}_{unique_id}")
    local_image_dir = os.path.join(output_dir, "images")

    # 确保目录存在
    os.makedirs(local_image_dir, exist_ok=True)

    # 获取PDF文件名（不含扩展名）
    name_without_suff = os.path.splitext(os.path.basename(pdf_file_path))[0]

    # 设置相对图片路径
    image_dir = "images"

    # 创建数据写入器
    image_writer = FileBasedDataWriter(local_image_dir)
    md_writer = FileBasedDataWriter(output_dir)

    # 读取PDF文件
    reader = FileBasedDataReader("")
    pdf_bytes = reader.read(pdf_file_path)

    # 创建数据集实例
    ds = PymuDocDataset(pdf_bytes)

    # 根据PDF类型进行处理
    if ds.classify() == SupportedPdfParseMethod.OCR:
        infer_result = ds.apply(doc_analyze, ocr=True)
        pipe_result = infer_result.pipe_ocr_mode(image_writer)
    else:
        infer_result = ds.apply(doc_analyze, ocr=False)
        pipe_result = infer_result.pipe_txt_mode(image_writer)

    # 只输出content_list.json和markdown文件
    pipe_result.dump_md(md_writer, f"{name_without_suff}.md", image_dir)
    pipe_result.dump_content_list(md_writer, f"{name_without_suff}_content_list.json", image_dir)

    print(f"处理完成！输出文件保存在: {output_dir}")
    return output_dir


if __name__ == "__main__":
    # 直接在这里指定PDF文件路径
    pdf_path = input("请输入PDF文件路径: ")

    if not os.path.exists(pdf_path):
        print(f"错误: 文件 '{pdf_path}' 不存在")
        sys.exit(1)

    output_path = process_pdf(pdf_path)
    print(f"输出目录: {output_path}")
