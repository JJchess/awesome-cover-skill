# ==========================================
# 依赖提示:
# 请确保安装了以下库 (注意这里我们升级为新的 google-genai 库以支持 Nano Banana):
# pip install google-genai python-dotenv pillow
# ==========================================
import os
import logging
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 1. 封面生成引擎 (使用 Nano Banana 文生图)
# ==========================================
class CoverEngine:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        if not self.use_mock:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                logging.warning("未在 .env 中找到 GEMINI_API_KEY，将回退到 Mock 模式。")
                self.use_mock = True
            else:
                # 使用最新的 genai SDK
                self.client = genai.Client(api_key=api_key)
                # 使用官方指定的 Nano Banana 模型
                self.model_id = "gemini-3.1-flash-image-preview"

    def _generate_fallback_image(self, title: str, subtitle: str, output_path: str):
        """当 API 失败时，使用 Pillow 绘制简单的 Fallback 封面"""
        logging.info("使用 Fallback 模式生成本地图片...")
        width, height = 800, 450
        img = Image.new("RGB", (width, height), color="#2C3E50")
        draw = ImageDraw.Draw(img)
        
        # 尝试加载默认字体
        try:
            font_lg = ImageFont.truetype("arial.ttf", 40)
            font_md = ImageFont.truetype("arial.ttf", 20)
        except:
            font_lg = ImageFont.load_default()
            font_md = ImageFont.load_default()

        draw.text((50, 150), title, fill="#FFFFFF", font=font_lg)
        draw.text((50, 220), subtitle, fill="#CCCCCC", font=font_md)
        
        img.save(output_path)
        logging.info(f"✅ Fallback 封面生成成功: {output_path}")

    def generate(self, title: str, subtitle: str, output_path: str):
        if self.use_mock:
            self._generate_fallback_image(title, subtitle, output_path)
            return

        try:
            # 构建文生图 Prompt (顶级设计师海报风，多元化艺术风格，水平排版位置自由，4:3偏高卡片比例)
            prompt = (
                f"Act as a world-class graphic designer. Create a highly diverse, visually breathtaking course cover poster. "
                f"Crucial requirements: "
                f"1. Typography: You MUST write the exact text '{title}' on the poster. Use a clean, modern, flat sans-serif font. NO 3D effects, NO bevels. "
                f"The text must be read horizontally (left-to-right). You have complete creative freedom to place this text anywhere in the composition (top, bottom, off-center, integrated into the environment) as long as it looks like a professional poster design. "
                f"2. Core Concept: '{subtitle}'. Interpret this concept into a stunning visual metaphor. "
                f"3. Artistic Diversity & Vibe: Make it look like an award-winning Behance/Dribbble portfolio piece. Break out of predictable layouts! "
                f"For each prompt, invent a totally unique art direction: it could be a surreal 3D glassmorphism setup, a moody cyberpunk scene, an elegant Swiss-style abstract vector graphic, or a high-tech minimalist UI concept. "
                f"4. Subject-Specific Color Palette: Give the poster ONE dominant, striking color identity that fits the subject perfectly (e.g., fiery orange for Rust, neon green for Finance, vivid magenta/cyan for UI), but feel free to mix in bold, unexpected accent colors. "
                f"5. Composition: Masterful 4:3 standard poster/card composition, striking a perfect balance between creative chaos and negative space."
            )
            
            logging.info(f"正在调用 Nano Banana ({self.model_id}) 生成图片: {title}")
            
            # 使用官方示例的 generate_content 方法
            # 我们在 prompt 里强调了 4:3 的构图，使其高度相对 16:9 更高
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
            )
            
            image_saved = False
            # 直接按照官方示例遍历 response.parts
            for part in response.parts:
                if part.text is not None:
                    logging.info(f"模型返回的文本: {part.text}")
                elif part.inline_data is not None:
                    # part.inline_data.data 包含了 base64 编码的字符串数据
                    # 我们需要将其解码为真实的二进制图片字节，然后写入文件
                    image_data = base64.b64decode(part.inline_data.data)
                    
                    # 确保是严格的 4:3 比例 (高度更接近宽度)，使用 Pillow 进行中心裁剪
                    img = Image.open(BytesIO(image_data))
                    width, height = img.size
                    target_ratio = 4 / 3
                    current_ratio = width / height
                    
                    if current_ratio > target_ratio + 0.01:
                        # 图片太宽，需要裁剪左右
                        new_width = int(height * target_ratio)
                        left = (width - new_width) // 2
                        right = left + new_width
                        img = img.crop((left, 0, right, height))
                    elif current_ratio < target_ratio - 0.01:
                        # 图片太高，需要裁剪上下
                        new_height = int(width / target_ratio)
                        top = (height - new_height) // 2
                        bottom = top + new_height
                        img = img.crop((0, top, width, bottom))
                        
                    # 裁剪完成后保存
                    img.save(output_path, format="JPEG", quality=95)
                    
                    image_saved = True
                    logging.info(f"✅ 封面生成成功 (4:3 卡片比例): {output_path}")
                    break # 只保存第一张图片
            
            if not image_saved:
                raise Exception("API 返回成功，但没有找到图片数据。")
            
        except Exception as e:
            logging.error(f"调用 Nano Banana 生成图片失败: {e}")
            self._generate_fallback_image(title, subtitle, output_path)


# ==========================================
# 2. 工作流主程序
# ==========================================
def run_batch_test(test_cases):
    engine = CoverEngine()

    # 将输出目录修改为项目根目录下的 output
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for i, case in enumerate(test_cases):
        print(f"\n正在处理第 {i+1} 个用例: {case['title']}")
        
        out_name = os.path.join(output_dir, f"cover_{i+1}.jpg")
        engine.generate(case["title"], case["subtitle"], out_name)

if __name__ == "__main__":
    test_cases = [
        {"title": "Rust 内存模型深度拆解", "subtitle": "所有权、生命周期与无畏并发"},
        {"title": "金融时间序列与冲击预测", "subtitle": "基于异质冲击编码的波动率量化模型"},
        {"title": "Agentic UI：下一代交互范式", "subtitle": "从静态卡片流到动态画布(Canvas)的工作流演进"},
        {"title": "Kubernetes 架构与实战", "subtitle": "云原生时代的容器编排与集群管理"},
        {"title": "Generative AI 艺术指南", "subtitle": "利用扩散模型创造惊艳的视觉资产"},
        {"title": "游戏引擎开发揭秘", "subtitle": "从图形渲染到物理碰撞的底层原理"}
    ]

    run_batch_test(test_cases)