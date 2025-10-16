import json
import logging
import base64
import io

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from wxcloudrun.models import Counters
from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger('log')


def index(request, _):
    """
    获取主页

     `` request `` 请求对象
    """

    return render(request, 'index.html')


def counter(request, _):
    """
    获取当前计数

     `` request `` 请求对象
    """

    rsp = JsonResponse({'code': 0, 'errorMsg': ''}, json_dumps_params={'ensure_ascii': False})
    if request.method == 'GET' or request.method == 'get':
        rsp = get_count()
    elif request.method == 'POST' or request.method == 'post':
        rsp = update_count(request)
    else:
        rsp = JsonResponse({'code': -1, 'errorMsg': '请求方式错误'},
                           json_dumps_params={'ensure_ascii': False})
    logger.info('response result: {}'.format(rsp.content.decode('utf-8')))
    return rsp


def get_count():
    """
    获取当前计数
    """

    try:
        data = Counters.objects.get(id=1)
    except Counters.DoesNotExist:
        return JsonResponse({'code': 0, 'data': 0},
                            json_dumps_params={'ensure_ascii': False})
    return JsonResponse({'code': 0, 'data': data.count},
                        json_dumps_params={'ensure_ascii': False})


def update_count(request):
    """
    更新计数，自增或者清零

    `` request `` 请求对象
    """

    logger.info('update_count req: {}'.format(request.body))

    body_unicode = request.body.decode('utf-8')
    body = json.loads(body_unicode)

    if 'action' not in body:
        return JsonResponse({'code': -1, 'errorMsg': '缺少action参数'},
                            json_dumps_params={'ensure_ascii': False})

    if body['action'] == 'inc':
        try:
            data = Counters.objects.get(id=1)
        except Counters.DoesNotExist:
            data = Counters()
        data.id = 1
        data.count += 1
        data.save()
        return JsonResponse({'code': 0, "data": data.count},
                            json_dumps_params={'ensure_ascii': False})
    elif body['action'] == 'clear':
        try:
            data = Counters.objects.get(id=1)
            data.delete()
        except Counters.DoesNotExist:
            logger.info('record not exist')
        return JsonResponse({'code': 0, 'data': 0},
                            json_dumps_params={'ensure_ascii': False})
    else:
        return JsonResponse({'code': -1, 'errorMsg': 'action参数错误'},
                            json_dumps_params={'ensure_ascii': False})


@csrf_exempt
def generate_image(request, _):
    """
    图生图接口 - 使用Google Gemini生成图片
    
    `` request `` 请求对象
    请求参数:
    - prompt: 文本提示词
    - image: base64编码的图片数据
    """

    logger.info('generate_image req: {}'.format(request.body))

    if request.method != 'POST':
        return JsonResponse({'code': -1, 'errorMsg': '只支持POST请求'},
                            json_dumps_params={'ensure_ascii': False})

    try:
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        # 检查必要参数
        if 'prompt' not in body:
            return JsonResponse({'code': -1, 'errorMsg': '缺少prompt参数'},
                                json_dumps_params={'ensure_ascii': False})

        if 'image' not in body:
            return JsonResponse({'code': -1, 'errorMsg': '缺少image参数'},
                                json_dumps_params={'ensure_ascii': False})

        prompt = body['prompt']
        image_data = body['image']

        # 解码base64图片数据
        try:
            # 移除data:image/...;base64,前缀（如果存在）
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            logger.error('图片解码失败: {}'.format(str(e)))
            return JsonResponse({'code': -1, 'errorMsg': '图片数据格式错误'},
                                json_dumps_params={'ensure_ascii': False})

        # 初始化Google Gemini客户端
        client = genai.Client()

        # 调用Gemini图生图接口
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[prompt, image],
        )

        # 处理响应
        generated_images = []
        for part in response.candidates[0].content.parts:
            if part.text is not None:
                logger.info('生成文本: {}'.format(part.text))
            elif part.inline_data is not None:
                # 将生成的图片转换为base64
                generated_image = Image.open(io.BytesIO(part.inline_data.data))
                buffer = io.BytesIO()
                generated_image.save(buffer, format='PNG')
                img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                generated_images.append(img_base64)

        if not generated_images:
            return JsonResponse({'code': -1, 'errorMsg': '未生成图片'},
                                json_dumps_params={'ensure_ascii': False})

        return JsonResponse({
            'code': 0,
            'data': {
                'images': generated_images,
                'count': len(generated_images)
            }
        }, json_dumps_params={'ensure_ascii': False})

    except json.JSONDecodeError:
        return JsonResponse({'code': -1, 'errorMsg': 'JSON格式错误'},
                            json_dumps_params={'ensure_ascii': False})
    except Exception as e:
        logger.error('图生图接口错误: {}'.format(str(e)))
        return JsonResponse({'code': -1, 'errorMsg': '服务器内部错误'},
                            json_dumps_params={'ensure_ascii': False})
