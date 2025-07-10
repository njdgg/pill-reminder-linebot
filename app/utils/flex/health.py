# app/utils/flex/health.py - 升級版本

from linebot.models import (
    FlexSendMessage, BubbleContainer, BoxComponent,
    TextComponent, ButtonComponent, URIAction, SeparatorComponent
)

def generate_health_log_menu(liff_url: str):
    """
    生成美化的「健康紀錄」選單，專注於主要功能。
    採用0705項目的現代化設計風格。
    """
    bubble = BubbleContainer(
        size='kilo',
        header=BoxComponent(
            layout='vertical',
            contents=[
                BoxComponent(
                    layout='horizontal',
                    contents=[
                        TextComponent(
                            text='💊',
                            size='xl',
                            flex=0,
                            margin='none'
                        ),
                        TextComponent(
                            text='健康紀錄',
                            weight='bold',
                            size='xl',
                            color='#FFFFFF',
                            margin='sm',
                            flex=1
                        )
                    ],
                    align_items='center'
                )
            ],
            padding_all='20px',
            background_color='#4A90E2',
            corner_radius='12px'
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                BoxComponent(
                    layout='vertical',
                    contents=[
                        TextComponent(
                            text='📊 記錄健康數據',
                            size='md',
                            color='#333333',
                            weight='bold',
                            margin='none'
                        ),
                        TextComponent(
                            text='血壓、血糖、體重等健康指標',
                            size='sm',
                            color='#666666',
                            margin='xs'
                        )
                    ],
                    margin='lg'
                ),
                SeparatorComponent(
                    margin='lg',
                    color='#E8E8E8'
                ),
                BoxComponent(
                    layout='vertical',
                    contents=[
                        TextComponent(
                            text='📈 查看歷史趨勢',
                            size='md',
                            color='#333333',
                            weight='bold',
                            margin='none'
                        ),
                        TextComponent(
                            text='圖表分析，掌握健康變化',
                            size='sm',
                            color='#666666',
                            margin='xs'
                        )
                    ],
                    margin='lg'
                ),
                SeparatorComponent(
                    margin='lg',
                    color='#E8E8E8'
                ),
                BoxComponent(
                    layout='vertical',
                    contents=[
                        TextComponent(
                            text='👨‍👩‍👧‍👦 家人健康管理',
                            size='md',
                            color='#333333',
                            weight='bold',
                            margin='none'
                        ),
                        TextComponent(
                            text='為家人記錄，關愛更貼心',
                            size='sm',
                            color='#666666',
                            margin='xs'
                        )
                    ],
                    margin='lg'
                )
            ],
            padding_all='20px',
            spacing='none'
        ),
        footer=BoxComponent(
            layout='vertical',
            spacing='md',
            contents=[
                ButtonComponent(
                    style='primary',
                    height='md',
                    action=URIAction(
                        label='🏥 開始使用健康紀錄',
                        uri=liff_url
                    ),
                    color='#4A90E2',
                    margin='none'
                )
            ],
            padding_all='20px'
        ),
        styles={
            'header': {'separator': False},
            'body': {'separator': False},
            'footer': {'separator': False}
        }
    )
    
    return FlexSendMessage(alt_text="健康記錄管理", contents=bubble)