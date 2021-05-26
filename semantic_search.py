#-*- coding:utf-8 -*-
import sys
from flask import Flask
from flask import request
from flask import jsonify
import dateparser
from dateparser.search import search_dates
import pandas as pd
import copy
from itertools import product
import json
from gensim.models import KeyedVectors

#sys.setdefaultencoding('utf-8')

similar_model = KeyedVectors.load_word2vec_format('./ko.bin.gz', binary=True)
print("similar_model is successfully loaded!")
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

attributeDictionary = {
    'title' : 'title',
    'description' : 'description'
}

# input : 사용자 쿼리
# output : attribute 별 query split
def splitter(query):
    resultDict = {}
    resultDict["query"] = []
    queryList = query.split()
    flag = ""
    for idx, word in enumerate(queryList):
        if word == "::":
            if flag != "":
                resultDict[attributeDictionary[flag]].pop()
            if flag == "":
                resultDict["query"].extend(queryList[:idx-1])
            flag = queryList[idx-1]
            continue
        if flag:
            if attributeDictionary[flag] not in resultDict.keys():
                resultDict[attributeDictionary[flag]] = []
            resultDict[attributeDictionary[flag]].append(word)
    # 마지막까지 search 할 때 attribute 안나오면 전부 담기
        if idx == (len(queryList) - 1) and flag is "":
            resultDict["query"].extend(queryList)
    return resultDict

#input : splitter 의 output (쿼리가 구분된 객체)
#desc : splitter 의 결과물에서 날짜 데이터를 찾음.
#output : 날짜 데이터가 찾아진 객체 반환
def requestDateParser(data):
    jsonData = data.copy()
    for key, value in data.items():
        request = " ".join(value)
        # DateParser 요청
        dates = search_dates(request,languages=['ko','en'])
        # 특정 개체가 DateParser 에 부합하는 걸 알면
        for val in value:
            if (dates is not None) and (val == dates[0][0]):
                if "dates" not in jsonData:
                    jsonData["dates"] = []
                    jsonData["datesKor"]=[]
                jsonData["dates"].append(str(dates[0][1]))
                jsonData["datesKor"].append(dates[0][0])
    return jsonData

#input : 장소 인지 여부를 파악할 문자열
#desc : 입력 문자열이 장소를 의미하는 지 여부 파악
#output : True / False
def isLocation(str):
    #지역 정보 로딩, 시 군 구를 포함함.
    df = pd.read_csv('./edit_location.csv',encoding='utf-8-sig')

    flag = False

    #일치하는 것이 나오면 flag를 True로 변환 후 리턴
    if str in " ".join(df['name'].tolist()):
        flag = True

    return flag

#input : requestDateParser 의 output (날짜를 인식한 객체)
#desc : 날짜를 인식한 객체에서 추가로 장소를 인식
#output : 장소를 인식한 객체 반환
def requestPlaceParser(data):
    jsonData = copy.deepcopy(data)
    for key, value in data.items():
        # 특정 개체가 PlaceParser 에 부합하는 걸 알면
        for val in value:
            if type(val) is str:

                if isLocation(val):
                    if "places" not in jsonData.keys():
                        jsonData["places"] = []
                    jsonData["places"].append(val)
    return jsonData


# input : query : splitter 에서 쪼갠 단어들, model : 학습된 모델
# desc : 모델을 통해 동의어 및 유사어 리스트 반환
# output : 동의어 / 유사어 가 포함된 list
def getSimilarWords(query, model):
    resultList = []
    try:
        results = model.most_similar(query)

        for result in results:
            if result[1] > 0.7:
                print(result)
                resultList.append(result[0])
    except:
        resultList = []
    return resultList

#input data : splitter, date/place parser 를 거친 객체, analyzer : 쿼리 분석기, model: 학습된 모델
#desc : getSimilarWords 모듈을 통해 동의어 및 유사어 리스트를 반환하여 질의 확장
#output : 질의가 확장된 객체
def requestSimilarWords(data, analyzer,model):
    requestDictionary = {}
    tempDict = {}
    for key, value in data.items():
        for val in value:
            tempDict[val] =[val]
        requestDictionary[key] = tempDict
        tempDict = {}

    for key, value in requestDictionary.items():
        for subkey, subvalue in value.items():
            if 'datesKor' not in analyzer.keys():

                subvalue.extend(getSimilarWords(subvalue[0],model))
            elif subvalue[0] not in analyzer['datesKor']:

                subvalue.extend(getSimilarWords(subvalue[0],model))
    temp = copy.deepcopy(requestDictionary)
    if 'dates' in analyzer.keys():
        temp['dates'] = copy.deepcopy(analyzer['dates'])
        temp['datesKor'] = copy.deepcopy(analyzer['datesKor'])
    if 'places' in analyzer.keys():
        temp['placesKor'] = copy.deepcopy(analyzer['places'])
    return requestDictionary, temp

#input : 동의어 및 유의어 리스트가 포함된 객체
#desc : 동의어 및 유의어 리스트를 조합하여 새로운 질의 생성
#output : 새로운 질의 리스트 객체
def mergeKeywords(data):
    keywords = {}
    totalList = []
    for key, value in data.items():
        if bool(value) == False:
            keywords[key] = value
            continue
        for subkey, subvalue in value.items():
            totalList.append(subvalue)
        keywords[key] = list(product(*totalList))
        totalList = []
    return keywords



#word2vec model
@app.route("/word")
def wordRouter():
    query = request.args.get('input')
    print(query)
    result = splitter(query)
    queryAnalyzer = requestDateParser(result)
    queryAnalyzer = requestPlaceParser(queryAnalyzer)
    similarWords, queryAnalyzer = requestSimilarWords(result, queryAnalyzer,similar_model)
    keywordList = mergeKeywords(similarWords)

    result = {
        "keywordList" : keywordList
    }
    resultList = []
    resultList.append(result)
    print(resultList)


    return jsonify(resultList)


#word2vec model
@app.route("/queryAnalyzer")
def queryAnalyzerRouter():
    query = request.args.get('input')

    result = splitter(query)
    queryAnalyzer = requestDateParser(result)
    queryAnalyzer = requestPlaceParser(queryAnalyzer)
    similarWords, queryAnalyzer = requestSimilarWords(result, queryAnalyzer,similar_model)
    keywordList = mergeKeywords(similarWords)

    result = json.dumps(queryAnalyzer, sort_keys=True, indent=4, ensure_ascii=False)
    return result






if __name__ == '__main__':
    app.run()
