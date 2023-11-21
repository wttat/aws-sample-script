import os
import random
from flask import Flask, render_template , send_from_directory, request , jsonify
import paddleocr
from paddleocr import PaddleOCR, draw_ocr
import boto3
import json

app = Flask(__name__,template_folder="templates")

@app.route('/dataset/<filename>')
def dataset(filename):
    return send_from_directory('dataset', filename)

@app.route('/')  
def index():
    # 随机选择图片
    folder_path = './dataset'
    file_names = os.listdir(folder_path)
    jpg_files = [file for file in file_names if file.endswith('.jpg')]
    random_file = random.choice(jpg_files)
    return render_template('index.html', image_file=random_file)


@app.route('/get_ocr_results')
def get_ocr_results():
    file_name = request.args.get('file_name', '')
    img_path = os.path.join('dataset', file_name)


    # OCR识别
    ocr = PaddleOCR(use_angle_cls=True, lang="ch")  
    result = ocr.ocr(img_path, cls=True) 
    # print (result)


    # 调用Claude生成描述
    new_result = remove_confidence(result) # 去掉置信度
    # print (new_result)
    
    prompt = generate_prompt(new_result)
    # print ("/n/nprompt"+prompt)

    
    bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-west-2',endpoint_url='https://bedrock-runtime.us-west-2.amazonaws.com')
    modelId = 'anthropic.claude-v2'

    response = call_claude(prompt, modelId, bedrock)
    completion = get_completion(response)

    # print (completion)
    # 展示结果
    return jsonify({
        'captions': completion
    })

def remove_confidence(data_list):
    print (data_list)
    new_list = []
    
    # Helper recursive function to delve into the nested lists
    def process_item(item):
        # Check if this is the list containing the tuple with confidence
        if isinstance(item, list) and len(item) == 2 and isinstance(item[1], tuple):
            coordinates = item[0]
            text = item[1][0]  # Only take the text part, discard the confidence score
            return [coordinates, text]
        elif isinstance(item, list):
            return [process_item(subitem) for subitem in item]
        else:
            return item
    
    # Process each item using the helper function
    for item in data_list:
        new_list.append(process_item(item))
    
    return new_list

def generate_prompt(ocr_result):
    print (ocr_result)
    prompt = """\n\nHuman:
    任务描述：
    1.解析输入的列表,这个列表是一个OCR程序识别小票后返回的结果。列表中的每个item包含了文字在小票中的相对位置、文字和识别置信度。忽略识别置信度。识别文本所在位置和文字之间的相对关系。
    2.规格化识别的文本框以及文字结果：将可能断行的中文文字，根据文本框的相对位置，拼接成完整的句子。将可能断行的日期，根据文本框的相对位置，拼接为完整的日期。识别关键字段，包括： "门店名称", "门店地址", "日期", "流水号", "应收金额", "实收", "优惠", "会员卡号", "药品信息"。

    请注意规格化识别汇总的规则:
    <rule>
    1.位于最上方第一行或者第二行的文本框中的文字，代表内容是“门店名称”，不可能包含"再打印"相关文字。
    2.日期一般是以"日期:"开头。并且遵循YYYYMMDD HH:MM:SS的格式,DD和HH中间有一个空格。
    3."流水号", "应收", "实收", "优惠", "会员卡号",这几个字段对应的值为纯数字,没有汉字或其他类别字符。
    4.实收总额和收款总额不同，收款总额减去找零即为实收总额。
    5.药品信息可能有多条，包含多种药品，请都包含在药品信息这个字段中。
    6.注意区分收货地址与门店地址这两个字段的不同。收货地址可能为空，而门店地址通常不为空。门店地址通常在最后出现。
    </rule>

    请注意输出格式要求:
    <format>
    1.如果没有识别到具体内容的字段，请用空字符串代替。
    2.严格以键值对的格式直接输出内容。
    3.不要生成识别以外的内容，不要编造关键字段以外的字段。
    4.输出需要放在<answer></answer> XML标签内。
    </format>

    请查看示例:
    <example>
    '门店名称': '',
     '门店地址': '',
     '日期': '',
     '流水号': '',
     '应收': '',
     '实付': '',
     '优惠': '',
     '会员卡号': '',
     '药品信息': ''
    </example>

    ## 输入如下:
    <input>
    %s
    </input>
    \n\nAssistant:
    """%ocr_result

    return prompt
    
def call_claude(prompt, modelId, bedrock):
    contentType = 'application/json'
    body = json.dumps({ "prompt":prompt,
                   "max_tokens_to_sample": 3000,
                   "temperature": 0.1,
                   "top_k": 250,
                   "top_p": 1,
                   "stop_sequences": []
                  }) 
    response = bedrock.invoke_model(body=body, modelId=modelId, contentType=contentType)
    response_body = json.loads(response.get('body').read())
    print (response_body.get("completion"))
    return response_body.get("completion")

def get_completion(response):
    completion = response.strip(" <answer>")
    completion = completion.strip("</answer>")
    return completion
    
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)

