# --- 請用此最終版本【完整覆蓋】您的 app/utils/flex/family.py ---

from linebot.models import (
    FlexSendMessage, BubbleContainer, CarouselContainer, BoxComponent,
    TextComponent, ButtonComponent, SeparatorComponent,
    PostbackAction, MessageAction, URIAction,
    QuickReply, QuickReplyButton
)
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from flask import current_app

def create_family_binding_menu():
    """產生家人綁定功能的專業選單。"""
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='lg',
            contents=[
                TextComponent(text='👨‍👩‍👧‍👦 家人綁定與管理', weight='bold', size='xl', color='#1F2937', align='center'),
                TextComponent(text='透過邀請碼建立家庭健康管理網路', color='#64748B', size='sm', align='center', wrap=True, margin='md'),
                SeparatorComponent(margin='lg'),
                BoxComponent(
                    layout='vertical', spacing='md', margin='lg',
                    contents=[
                        ButtonComponent(
                            action=PostbackAction(label='🎫 產生邀請碼', data='action=gen_code'),
                            style='primary', color='#10B981', height='md'
                        ),
                        ButtonComponent(
                            action=PostbackAction(label='👥 管理我的家人', data='action=manage_family'),
                            style='secondary', height='md', margin='sm'
                        )
                    ]
                ),
                SeparatorComponent(margin='lg'),
                BoxComponent(
                    layout='vertical', spacing='xs', margin='md',
                    contents=[
                        TextComponent(text='💡 小提示', size='sm', weight='bold', color='#374151'),
                        TextComponent(text='• 邀請碼有效期為10分鐘。', size='xs', color='#6B7280', margin='xs'),
                        TextComponent(text='• 家人輸入「綁定 [邀請碼]」即可開始流程。', size='xs', color='#6B7280', wrap=True),
                        TextComponent(text='• 綁定後即可為家人設定用藥提醒與藥歷。', size='xs', color='#6B7280', wrap=True)
                    ]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="家人綁定選單", contents=bubble)

def create_invite_code_flex(code: str):
    """
    【最終修正版】產生分享邀請碼的 Flex Message，並在分享內容中包含可點擊的快捷連結。
    """
    bot_id = current_app.config['YOUR_BOT_ID']
    
    # 1. 準備要自動填入的指令文字
    oa_message_text = f"綁定 {code}"
    # 2. 對指令文字進行 URL 編碼
    oa_message_encoded = quote(oa_message_text)
    # 3. 組成【快捷連結】
    binding_url = f"https://line.me/R/oaMessage/{bot_id}/?{oa_message_encoded}"

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).astimezone(timezone(timedelta(hours=8)))
    expires_at_str = expires_at.strftime("%H:%M")

    # 4. 準備包含【快捷連結】的完整分享訊息
    share_message = f"""🏠 家庭健康小幫手邀請

您好！我想邀請您加入我的家庭健康管理系統。

📱 請點擊下方連結完成綁定：
{binding_url}

或直接在聊天室輸入：
綁定 {code}

⏰ 邀請碼有效期限至 {expires_at_str}"""

    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='lg',
            contents=[
                TextComponent(text='✉️ 家人邀請碼', weight='bold', size='xl', color='#1F2937', align='center'),
                BoxComponent(
                    layout='vertical', background_color='#F8FAFC', corner_radius='12px',
                    padding_all='16px', margin='md',
                    contents=[
                        TextComponent(text='您的邀請碼', size='sm', color='#64748B', align='center'),
                        TextComponent(text=f"{code}", weight='bold', size='xxl', color='#3B82F6', align='center', margin='sm'),
                        TextComponent(text=f"有效期限至 {expires_at_str}", size='xs', color='#64748B', align='center', margin='sm')
                    ]
                ),
                # 5. 將完整的分享訊息用於分享按鈕
                ButtonComponent(
                    action=URIAction(label='📤 立即分享給家人', uri=f"https://line.me/R/share?text={quote(share_message)}"),
                    style='primary', color='#10B981', height='md'
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="家人邀請碼已產生", contents=bubble)

def create_binding_confirmation_flex(code: str):
    """產生邀請碼確認的專業 Flex Message。"""
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='lg',
            contents=[
                TextComponent(text='🔐 綁定確認', weight='bold', size='xl', color='#1F2937', align='center'),
                BoxComponent(
                    layout='vertical', background_color='#FEF3C7', corner_radius='12px',
                    padding_all='16px', margin='md',
                    contents=[
                        TextComponent(text='收到邀請碼', size='sm', color='#92400E', align='center'),
                        TextComponent(text=f"{code}", weight='bold', size='xl', color='#D97706', align='center', margin='sm')
                    ]
                ),
                TextComponent(text="確定要與此邀請碼的使用者建立綁定關係嗎？", wrap=True, size='md', color='#374151', align='center', margin='md'),
                BoxComponent(
                    layout='horizontal', spacing='sm', margin='lg',
                    contents=[
                        ButtonComponent(
                            action=PostbackAction(label='取消', data='action=cancel_bind'),
                            style='secondary', flex=1
                        ),
                        ButtonComponent(
                            action=PostbackAction(label='確認綁定', data=f'action=confirm_bind&code={code}'),
                            style='primary', color='#10B981', flex=1
                        )
                    ]
                ),
                SeparatorComponent(margin='lg'),
                BoxComponent(
                    layout='vertical', spacing='xs', margin='sm',
                    contents=[
                        TextComponent(text='🛡️ 安全提示', size='sm', weight='bold', color='#374151'),
                        TextComponent(text='• 請確認邀請碼來源可信。', size='xs', color='#6B7280', margin='xs'),
                        TextComponent(text='• 綁定後對方可為您設定提醒。', size='xs', color='#6B7280')
                    ]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="邀請碼綁定確認", contents=bubble)

def create_family_manager_carousel(family_list: list):
    """產生管理已綁定家人的專業輪播 Flex Message。"""
    if not family_list:
        return FlexSendMessage(alt_text="家人管理", contents=BubbleContainer(
            body=BoxComponent(
                layout='vertical', padding_all='20px', spacing='lg',
                contents=[
                    TextComponent(text='👥 家人管理', weight='bold', size='xl', color='#1F2937', align='center'),
                    TextComponent(text='尚未綁定家人，開始邀請家人加入您的健康管理網路吧！', size='sm', color='#6B7280', wrap=True, margin='md', align='center'),
                    ButtonComponent(
                        action=PostbackAction(label='🎫 產生邀請碼', data='action=gen_code'),
                        style='primary', color='#10B981', margin='lg'
                    )
                ]
            )
        ))

    bubbles = []
    for member in family_list:
        nickname = member['relation_type']
        display_name = member.get('recipient_name', '家人')
        bubble = BubbleContainer(
            body=BoxComponent(
                layout='vertical', padding_all='20px', spacing='lg',
                contents=[
                    BoxComponent(
                        layout='vertical', background_color='#F8FAFC', corner_radius='12px', padding_all='16px',
                        contents=[
                            TextComponent(text='👤', size='xl', align='center'),
                            TextComponent(text=nickname, weight='bold', size='xl', align='center', color='#1F2937', margin='sm'),
                            TextComponent(text=f'姓名：{display_name}', size='sm', align='center', color='#64748B', margin='xs')
                        ]
                    ),
                    BoxComponent(
                        layout='vertical', spacing='sm', margin='lg',
                        contents=[
                            ButtonComponent(
                                action=PostbackAction(label='✏️ 修改稱謂', data=f"action=edit_nickname&nickname={quote(nickname)}"),
                                style='primary', color='#3B82F6', height='sm'
                            ),
                            ButtonComponent(
                                action=PostbackAction(label='🔗 解除綁定', data=f"action=delete_binding&nickname={quote(nickname)}"),
                                style='secondary', color='#EF4444', height='sm', margin='sm'
                            )
                        ]
                    )
                ]
            )
        )
        bubbles.append(bubble)
    
    add_invite_bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='lg', justify_content='center', align_items='center',
            contents=[
                TextComponent(text='➕', size='xxl', align='center', color='#10B981'),
                TextComponent(text='邀請更多家人', weight='bold', size='lg', align='center', color='#1F2937', margin='sm'),
                TextComponent(text='擴展您的家庭健康管理網路', size='sm', align='center', color='#64748B', wrap=True, margin='xs'),
                ButtonComponent(
                    action=PostbackAction(label='🎫 產生新邀請碼', data='action=gen_code'),
                    style='primary', color='#10B981', height='md', margin='lg'
                )
            ]
        )
    )
    bubbles.append(add_invite_bubble)
    
    return FlexSendMessage(alt_text="家人管理清單", contents=CarouselContainer(contents=bubbles))

def create_relation_quick_reply():
    """建立稱謂選擇的快速回覆按鈕。"""
    items = [
        QuickReplyButton(action=PostbackAction(label="爸爸", data="relation:爸爸", text="我選擇了「爸爸」")),
        QuickReplyButton(action=PostbackAction(label="媽媽", data="relation:媽媽", text="我選擇了「媽媽」")),
        QuickReplyButton(action=PostbackAction(label="兒子", data="relation:兒子", text="我選擇了「兒子」")),
        QuickReplyButton(action=PostbackAction(label="女兒", data="relation:女兒", text="我選擇了「女兒」")),
        QuickReplyButton(action=PostbackAction(label="其他", data="relation:other"))
    ]
    return QuickReply(items=items)