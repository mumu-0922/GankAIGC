def test_word_formatter_billing_routes_are_unavailable_when_feature_disabled(client):
    responses = [
        client.post(
            "/api/word-formatter/format/text",
            json={
                "text": "测试论文标题\n\n这是用于 Word 排版计费测试的正文段落。",
                "billing_mode": "platform",
                "include_cover": False,
                "include_toc": False,
            },
        ),
        client.post(
            "/api/word-formatter/specs/generate",
            json={
                "requirements": "标题三号黑体居中，正文小四号宋体。",
                "billing_mode": "platform",
            },
        ),
        client.post(
            "/api/word-formatter/preprocess/text",
            json={
                "text": "测试论文标题\n\n这是用于 Word 预处理计费测试的正文段落。",
                "billing_mode": "platform",
            },
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]
