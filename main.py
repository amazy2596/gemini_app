import time
import json
from flask import Flask, request, jsonify
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import threading
from pathlib import Path
import random

# ==============================================================================
# --- 配置区 ---
# ==============================================================================
project_dir = Path(__file__).parent.resolve()
CHROME_PROFILE_PATH = str(project_dir / 'selenium_chrome_profile')
CHROME_DRIVER_NAME = 'chromedriver.exe'  # 手动下载的 ChromeDriver 名称
AI_STUDIO_URL = "https://aistudio.google.com/prompts/new_chat"


# ==============================================================================
# --- 浏览器服务层 (封装所有 Selenium 操作) ---
# ==============================================================================
class GeminiWebService:
    def __init__(self):
        self.driver = None
        self.driver_ready_event = threading.Event()

    def setup_driver(self):
        """初始化并配置 undetectable_chromedriver (手动模式)"""
        try:
            # --- 核心改动：使用本地驱动，禁用网络检查 ---
            driver_path = project_dir / CHROME_DRIVER_NAME
            
            if not driver_path.is_file():
                print(f"--- ❌ 错误：在项目目录中未找到 {CHROME_DRIVER_NAME} ---")
                print("请按照说明手动下载正确的 ChromeDriver 并放置在项目文件夹中。")
                return

            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            
            # --- 新增：伪装成美国英语区用户 ---
            options.add_argument("--lang=en-US")

            # --- 关键修改：启用新的无头模式并添加增强参数 ---
            # options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            # options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
            
            print(f"Chrome 个人资料将保存在: {CHROME_PROFILE_PATH}")
            print("!!! 正在以“本地驱动模式”启动，已禁用网络版本检查 !!!")
            print(f"使用的驱动路径: {driver_path}")
            
            self.driver = uc.Chrome(driver_executable_path=str(driver_path), options=options)
            
            print(f"正在打开 {AI_STUDIO_URL}...")
            self.driver.get(AI_STUDIO_URL)
            
            # 无头模式下无法手动登录，你需要确保 CHROME_PROFILE_PATH 中已经保存了登录状态
            print("浏览器驱动已在无头模式下就绪。服务将依赖已保存的登录会话。")

            print("\n--- ✅ WebDriver 已准备就绪，服务可以接收请求 ---")
            self.driver_ready_event.set()

        except Exception as e:
            print(f"\n--- ❌ WebDriver 启动失败 ---")
            print("错误原因可能是：")
            print("1. 手动放置的 chromedriver.exe 版本和 Chrome 浏览器版本不兼容。")
            print("2. 在无头模式下，Google AI Studio 可能升级了检测机制。")
            print("3. 如果是首次在无头模式下运行，需要先以有头模式运行一次，登录 Google 账号，让 Selenium 保存 Cookie。")
            import traceback
            traceback.print_exc()

    def select_model(self, model_name: str):
        """在UI上动态选择模型 (v16 两步式选择)"""
        if not model_name:
            return
        try:
            print(f"步骤 0: 开始两步式模型选择 '{model_name}'...")
            wait = WebDriverWait(self.driver, 15)

            # --- 1. 解析模型名称，提取大类和关键词 ---
            category_text = ""
            # 识别主要版本作为大类
            if "2.5" in model_name: category_text = "GEMINI 2.5"
            elif "2.0" in model_name: category_text = "GEMINI 2.0"
            elif "1.5" in model_name: category_text = "GEMINI 1.5"
            elif "gemma" in model_name.lower(): category_text = "GEMMA"
            else: raise ValueError("无法从模型名称中解析出主版本类别。")
            
            # 提取除版本号和'gemini'外的其它关键词
            keywords_to_match = [
                kw for kw in model_name.lower().split('-') 
                if kw not in ['gemini', '2.5', '2.0', '1.5'] and kw
            ]
            print(f"解析结果 -> 大类: '{category_text}', 关键词: {keywords_to_match}")

            # --- 2. Selenium 操作 ---
            # 2.1. 点击主模型选择器打开面板
            main_selector_css = "ms-model-selector-two-column mat-select"
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, main_selector_css))).click()
            print("主下拉菜单已打开。")
            time.sleep(1) 

            # 2.2. 点击模型大类
            category_xpath = f"//div[contains(@class, 'model-category-container') and contains(., '{category_text}')]"
            wait.until(EC.element_to_be_clickable((By.XPATH, category_xpath))).click()
            print(f"已点击模型大类: '{category_text}'")
            time.sleep(1)

            # 2.3. 在右侧面板中根据所有关键词选择具体模型
            # 构建一个复杂的XPath，要求一个选项必须同时包含所有关键词
            model_xpath_base = "//mat-option"
            model_xpath_conditions = "".join([f"[contains(normalize-space(.), '{kw}')]" for kw in keywords_to_match])
            final_model_xpath = model_xpath_base + model_xpath_conditions
            
            print(f"正在使用 XPath 查找具体模型: {final_model_xpath}")
            wait.until(EC.element_to_be_clickable((By.XPATH, final_model_xpath))).click()

            print(f"已选择具体模型: '{model_name}'")

        except Exception as e:
            print(f"!!! 选择模型 '{model_name}' 时出错: {e} !!!")
            # 尝试点击一个空白处来关闭下拉框，以防干扰下次操作
            try: self.driver.find_element(By.TAG_NAME, 'body').click()
            except: pass
            raise ValueError(f"选择模型 '{model_name}' 失败。请检查名称，或UI结构已改变。")
    
    def chat(self, prompt: str, model: str) -> str:
        """执行核心的聊天操作并返回结果 (完全采用您提供的浏览器操作逻辑)"""
        # 1. 选择模型 (如果提供了模型名称)
        self.select_model(model)
        
        # prompt 参数是从 API 层传入的，不再从 request 中获取
        user_prompt = prompt
        print(f"提示: {user_prompt}")
        
        # 1. 定位输入框 (使用您偏好的选择器)
        print("步骤 1: 正在定位输入框...")
        prompt_input_css = 'text-wrapper'
        prompt_input = WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, prompt_input_css))
        )
        print("输入框定位成功。")

        # 2. 输入提示 (使用您偏好的慢速输入)
        print("步骤 2: 正在模拟真人慢速输入...")
        ActionChains(self.driver).move_to_element(prompt_input).click().perform()
        for char in user_prompt:
            ActionChains(self.driver).send_keys(char).perform()
            time.sleep(random.uniform(0.05, 0.15))
        print("提示输入完成。")

        # --- 新增：在点击前增加短暂的随机延迟 ---
        human_like_delay = random.uniform(0.5, 1.5)
        print(f"步骤 2.5: 模拟人类思考，等待 {human_like_delay:.2f} 秒...")
        time.sleep(human_like_delay)

        # 3. 点击发送按钮
        print("步骤 3: 正在点击发送按钮...")
        send_button_css = 'button.run-button'
        send_button = WebDriverWait(self.driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, send_button_css))
        )
        send_button.click()
        print("发送按钮点击成功。")
        
        # 4. 等待回复完成
        print("步骤 4: 正在等待模型回复...")
        stoppable_button_css = "button.run-button.stoppable"
        wait = WebDriverWait(self.driver, 15) # 使用短一点的超时进行状态检查
        
        try:
            print("步骤 4.1: 等待'生成中'状态出现...")
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, stoppable_button_css))
            )
            print("生成已开始。")

            print("步骤 4.2: 等待'生成中'状态结束...")
            # 这里使用更长的超时时间来等待模型真正完成
            WebDriverWait(self.driver, 600).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, stoppable_button_css))
            )
            print("模型回复已完成。")

        except Exception as e:
                # 如果在等待时就发生超时或错误，立即截图
                error_screenshot_path = project_dir / "wait_error.png"
                self.driver.save_screenshot(str(error_screenshot_path))
                print(f"--- ❌ 在等待生成过程中出错，已截图至: {error_screenshot_path} ---")
                # 重新抛出异常，中断当前流程
                raise e
        
        time.sleep(1)

        # 5. 提取回复文本 (使用您偏好的选择器和健壮性检查)
        print("步骤 5: 正在提取回复文本...")
        response_containers_css = 'model-prompt-container'
        response_containers = WebDriverWait(self.driver, 15).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, response_containers_css))
        )
        if not response_containers:
            # 在服务层，我们应该抛出异常，让API层去处理如何响应
            raise Exception("未能提取到模型回复，找不到任何回复容器。")
        
        final_answer = response_containers[-1].text.strip()

        # --- 新增：检查是否为已知错误，如果是则截图 ---
        if "internal error has occurred" in final_answer.lower():
            error_screenshot_path = project_dir / "headless_error.png"
            self.driver.save_screenshot(str(error_screenshot_path))
            print(f"--- ❌ 检测到内部错误，已截图至: {error_screenshot_path} ---")
            # 仍然抛出异常，让上层知道出错了
            raise Exception("Google AI Studio aistudio.google.com返回了内部错误。")

        if not final_answer:
            raise Exception("提取到的回复文本为空。")
        
        if not final_answer:
            raise Exception("提取到的回复文本为空。")
        
        print(f"提取到的回复: {final_answer}")
        
        # 在这里，函数应该返回最终的字符串结果
        return final_answer
        
    # ==================================================
    # --- TODO: 为您预留的待实现功能接口 ---
    # ==================================================
    def generate_image(self, prompt: str, model: str, n: int):
        print("收到图片生成请求，此功能待实现...")
        # TODO: 在这里添加您自己的 Selenium 逻辑来操控 UI 上的图片生成功能
        raise NotImplementedError("图片生成功能待您实现")

    def create_embedding(self, text: str, model: str):
        print("收到 Embedding 请求，此功能待实现...")
        # TODO: 在这里添加您自己的 Selenium 逻辑，可能需要切换到不同的页面或模式
        raise NotImplementedError("Embedding 功能待您实现")

# ==============================================================================
# --- API 服务层 (Flask App) ---
# ==============================================================================
app = Flask(__name__)
gemini_service = GeminiWebService()

# === API Endpoint: /models ===
@app.route('/v1beta/openai/models', methods=['GET'])
def list_models():
    """模拟官方接口，返回一个硬编码的模型列表"""
    print("收到模型列表请求...")
    # 您可以根据需要随时更新这个列表
    model_data = [
        {"id": "gemini-2.5-pro-preview", "object": "model", "owned_by": "google"},
        {"id": "gemini-2.5-pro", "object": "model", "owned_by": "google"},
        {"id": "gemini-2.5-flash-preview", "object": "model", "owned_by": "google"},
        {"id": "gemini-2.0-flash", "object": "model", "owned_by": "google"},
        # ... 其他模型
    ]
    return jsonify({"object": "list", "data": model_data})

# === API Endpoint: /models/{model_id} ===
@app.route('/v1beta/openai/models/<string:model_id>', methods=['GET'])
def retrieve_model(model_id):
    """模拟官方接口，返回单个模型的信息"""
    print(f"收到检索模型 {model_id} 的请求...")
    # 这里可以返回更详细的信息
    return jsonify({"id": model_id, "object": "model", "owned_by": "google"})

# === API Endpoint: /chat/completions ===
@app.route('/v1beta/openai/chat/completions', methods=['POST'])
def chat_completions():
    print("\n--- 收到 Chat Completion 新请求 ---")
    if not gemini_service.driver_ready_event.wait(timeout=60):
        return jsonify({"error": "WebDriver 仍在初始化中或启动失败"}), 503

    try:
        request_data = request.get_json()
        model = request_data.get("model")
        messages = request_data.get("messages", [])
        
        # TODO: 您可以在这里添加更多逻辑来处理函数调用、图片、音频等
        # 例如，解析 messages 列表，找到图片或音频数据
        user_prompt = " ".join([msg["content"] for msg in messages if msg["role"] == "user"])

        # 调用核心 chat 服务
        final_answer = gemini_service.chat(prompt=user_prompt, model=model)
        
        # 按照 OpenAI 格式构建响应
        response_payload = {
            "id": "chatcmpl-" + str(time.time()),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": final_answer,
                },
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        return jsonify(response_payload)

    except Exception as e:
        import traceback
        print("!!! 处理 Chat Completion 请求时发生严重错误 !!!")
        traceback.print_exc()
        return jsonify({"error": f"处理请求时发生未知错误: {e}"}), 500


# === API Endpoint: /images/generate (预留接口) ===
@app.route('/v1beta/openai/images/generate', methods=['POST'])
def images_generate():
    print("\n--- 收到 Image Generate 新请求 ---")
    try:
        request_data = request.get_json()
        prompt = request_data.get("prompt")
        model = request_data.get("model")
        n = request_data.get("n", 1)
        # 调用预留的 service 方法
        gemini_service.generate_image(prompt, model, n)
        # 由于未实现，这里只返回一个示意
        return jsonify({"message": "Image generation not implemented yet."})
    except NotImplementedError as e:
        return jsonify({"error": str(e)}), 501
    except Exception as e:
        return jsonify({"error": f"处理请求时发生未知错误: {e}"}), 500


# === API Endpoint: /embeddings (预留接口) ===
@app.route('/v1beta/openai/embeddings', methods=['POST'])
def embeddings():
    print("\n--- 收到 Embeddings 新请求 ---")
    try:
        request_data = request.get_json()
        text = request_data.get("input")
        model = request_data.get("model")
        # 调用预留的 service 方法
        gemini_service.create_embedding(text, model)
        return jsonify({"message": "Embeddings not implemented yet."})
    except NotImplementedError as e:
        return jsonify({"error": str(e)}), 501
    except Exception as e:
        return jsonify({"error": f"处理请求时发生未知错误: {e}"}), 500


# ==============================================================================
# --- 程序主入口 ---
# ==============================================================================
if __name__ == '__main__':
    driver_thread = threading.Thread(target=gemini_service.setup_driver)
    driver_thread.daemon = True
    driver_thread.start()
    
    # 使用和官方兼容的 URL 前缀
    print("Flask 服务已启动。API 将在 /v1beta/openai/ ... 路径下可用。")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)