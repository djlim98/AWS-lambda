from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import boto3
import re, requests

def create_driver(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1280x1696')
    chrome_options.add_argument('--user-data-dir=/tmp/user-data')
    chrome_options.add_argument('--hide-scrollbars')
    chrome_options.add_argument('--enable-logging')
    chrome_options.add_argument('--log-level=0')
    chrome_options.add_argument('--v=99')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--data-path=/tmp/data-path')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--homedir=/tmp')
    chrome_options.add_argument('--disk-cache-dir=/tmp/cache-dir')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36')
    chrome_options.binary_location = "/opt/python/bin/headless-chromium"
    driver = webdriver.Chrome('/opt/python/bin/chromedriver', chrome_options=chrome_options)
    driver.get(url)
    return driver

dynamodb = boto3.resource(
        "dynamodb",
    )
table=dynamodb.Table("gamePatchBot")    

def check_data(data):
    
    response = table.get_item(Key={"dataType": "kart","notification_id": data})
    print(response)
    try:
        item = response["Item"]
    except KeyError:
        return True
    
    return False

def find_recent_patch_list(driver):
    patchListElements = driver.find_elements_by_xpath('//*[@id="kart_main_sections"]//tbody//a')
    patchDateListElements = driver.find_elements_by_xpath('//*[@class="list_td day"]')
    patchList = []

    for index, val in enumerate(patchListElements):
        href = val.get_attribute("href")
        notificationId=int(href.split("n4articlesn=")[-1])
        if check_data(notificationId):
            text = val.get_attribute("text")
            patchDate = patchDateListElements[index].text
            patchList.append([text, href, patchDate])
        
    return patchList
    
def upload_data(driver, dataList):
    errList=[]
    for patch in dataList:
        link = patch[1]  # 세부사항 링크.
        driver.get(link)  # 링크 진입
        try:
            stringElement = driver.find_element_by_xpath('//*[@class="board_imgarea"]')
            noticeString = stringElement.text  # 게시글 내용 전부 긁어옴

            thumbnailElements = driver.find_elements_by_xpath('//*[@class="board_imgarea"]//img')
            thumbnailSrc = ""
            if len(thumbnailElements) > 0:
                thumbnailSrc = thumbnailElements[0].get_attribute("src")
            else:
                thumbnailSrc = "no imgs"
            subjectExpresion = re.compile("\d[.] .*\n")
            subjectList = list(
                map(lambda subject: subject.strip("\n"), subjectExpresion.findall(noticeString))
            )

            patch_contents = []
            patch_content = []
            subject_num = 0
            patchTime = noticeString.split("일정]")[1].split("\n")[1].split("\n")[0].strip("- ")
            for idx, line in enumerate(noticeString.splitlines()):
                if subjectList[subject_num] in line:
                    if subject_num != 0:
                        patch_contents.append(patch_content)
                        patch_content = []
                    if subject_num < len(subjectList) - 1:
                        subject_num += 1
                if "▶" in line:
                    patch_content.append(line.strip())
                if idx == len(noticeString.splitlines()) - 1:
                    patch_contents.append(patch_content)

            patchData = list(
                map(
                    lambda subject: {
                        "patch_subject": subject[1],
                        "patch_content": patch_contents[subject[0]],
                    },
                    tuple(enumerate(subjectList)),
                )
            )
            data = {
                "dataType": "kart",
                "notification_id": int(patch[1].split("n4articlesn=")[-1]),
                "date": patch[2],
                "thumbnail_src": thumbnailSrc,
                "subject": patch[0],
                "content": {"patch_list": patchData},
                "patchTime": patchTime,
            }
            print(data)

            table.put_item(Item=data)
            
        except Exception as ex:
            errList.append( ex, int(patch[1].split("n4articlesn=")[-1]))
            pass
        
    return errList

def lambda_handler(event, lambda_context):
    # TODO implement
    driver=create_driver('https://kart.nexon.com/Kart/News/Patch/List.aspx?n4pageno=1')
    
    recentPatchList=find_recent_patch_list(driver)
    print(recentPatchList)
    
    patchIdList=list(map(lambda patch: int(patch[1].split("n4articlesn=")[-1]), recentPatchList))
    errList=upload_data(driver, recentPatchList)
    
    data={"error":errList, "patchList":patchIdList,}
    
    response = requests.post("https://game-patch-bot.herokuapp.com/notification", json=data)
    print(response)
    return recentPatchList, errList
