# app/utils/flex/reminder.py

from linebot.models import (
    FlexSendMessage, BubbleContainer, CarouselContainer, BoxComponent,
    TextComponent, ButtonComponent, SeparatorComponent,
    PostbackAction, MessageAction, URIAction
)
from urllib.parse import quote
from flask import current_app

def create_reminder_management_menu():
    """【樣式復刻】產生用藥提醒管理的專業選單。"""
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='xl',
            contents=[
                TextComponent(text='🔔 用藥提醒管理', weight='bold', size='xl', align='center', color='#1F2937'),
                SeparatorComponent(margin='lg'),
                BoxComponent(
                    layout='vertical', margin='lg', spacing='md',
                    contents=[
                        ButtonComponent(
                            action=MessageAction(label='➕ 新增/查詢提醒', text='新增/查詢提醒'),
                            style='primary', color='#10B981', height='md'
                        ),
                        ButtonComponent(
                            action=MessageAction(label='👥 管理提醒對象', text='管理提醒對象'),
                            style='secondary', color='#3B82F6', height='md', margin='sm'
                        ),
                        ButtonComponent(
                            action=MessageAction(label='🗑️ 刪除提醒對象', text='刪除提醒對象'),
                            style='secondary', color='#EF4444', height='md', margin='sm'
                        ),
                        ButtonComponent(action=MessageAction(label='🔙 回到主選單', text='選單'), style='link', margin='lg')
                    ]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="用藥提醒管理選單", contents=bubble)

def create_member_management_carousel(members_summary: list, liff_manual_reminder_id: str):
    """
    【邏輯強化 & 樣式復刻】產生資訊高度整合的管理提醒對象輪播。
    """
    if not members_summary:
        return FlexSendMessage(alt_text="提醒對象管理", contents=BubbleContainer(
            body=BoxComponent(layout='vertical', padding_all='20px', spacing='lg', contents=[
                TextComponent(text='👥 提醒對象管理', weight='bold', size='xl', align='center'),
                TextComponent(text='尚未建立任何提醒對象。', size='sm', color='#6B7280', wrap=True, margin='md', align='center'),
                ButtonComponent(
                    action=PostbackAction(label='⊕ 新增第一位對象', data='action=add_member_profile'),
                    style='primary', color='#10B981', margin='lg'
                )
            ])
        ))

    bubbles = []
    members_sorted = sorted(members_summary, key=lambda m: 0 if m['member'] == '本人' else 1)

    for m in members_sorted:
        actions = []
        member_name_encoded = quote(m['member'])

        if m['member'] != '本人':
            actions.append(
                ButtonComponent(
                    action=PostbackAction(label='✏️ 修改名稱', data=f"action=rename_member_profile&member_id={m['id']}"),
                    style='primary', color='#3B82F6', height='sm'
                )
            )
        
        actions.append(
            ButtonComponent(
                action=MessageAction(label='🔍 查看提醒', text=m['member']),
                style='secondary', height='sm', margin='sm'
            )
        )
        
        if m.get('reminders_count', 0) > 0:
            actions.append(
                ButtonComponent(
                    action=PostbackAction(label='🧹 清空此對象提醒', data=f"action=clear_reminders_for_member&member_id={m['id']}"),
                    style='secondary', color='#F59E0B', height='sm', margin='sm'
                )
            )
        
        bubble = BubbleContainer(
            body=BoxComponent(
                layout='vertical', spacing='md',
                contents=[
                    TextComponent(text=m['member'], weight='bold', size='xl'),
                    TextComponent(text=f"💊 {m.get('reminders_count', 0)} 筆提醒", size='sm', color='#4CAF50' if m.get('reminders_count', 0) > 0 else '#999999', weight='bold'),
                    TextComponent(text=m.get('reminders_preview', '尚無提醒'), size='xs', color='#666666', wrap=True),
                    SeparatorComponent(margin='lg'),
                    BoxComponent(layout='vertical', spacing='sm', contents=actions)
                ]
            )
        )
        bubbles.append(bubble)

    add_bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', spacing='md', justify_content='center', align_items='center', height='250px',
            contents=[
                TextComponent(text='⊕', size='xxl', color='#10B981', weight='bold'),
                TextComponent(text='新增提醒對象', weight='bold', size='lg', margin='md'),
                ButtonComponent(
                    action=PostbackAction(label='點此新增', data='action=add_member_profile'),
                    style='primary', color='#10B981'
                )
            ]
        )
    )
    bubbles.append(add_bubble)
    
    return FlexSendMessage(alt_text="提醒對象管理", contents=CarouselContainer(contents=bubbles))

def create_reminder_list_carousel(member: dict, reminders: list, liff_manual_reminder_id: str):
    """【樣式復刻】產生特定成員的用藥提醒列表輪播"""
    if not reminders:
        liff_url = f"https://liff.line.me/{liff_manual_reminder_id}?mode=add&member_id={member['id']}"
        return FlexSendMessage(alt_text=f"為 {member['member']} 新增提醒", contents=BubbleContainer(
            body=BoxComponent(layout='vertical', spacing='md', padding_all='20px', contents=[
                TextComponent(text=f"為「{member['member']}」新增提醒", weight='bold', size='lg'),
                TextComponent(text='這位成員還沒有任何提醒！', wrap=True, size='sm', color='#64748B', margin='md'),
                ButtonComponent(action=URIAction(label='點此新增第一筆提醒', uri=liff_url), style='primary', color='#10B981')
            ])
        ))

    bubbles = []
    for r in reminders:
        time_slots = []
        for i in range(1, 6):
            time_val = r.get(f'time_slot_{i}')
            if time_val:
                # 處理 timedelta 和 datetime.time 物件
                if hasattr(time_val, 'total_seconds'): # timedelta
                    seconds = int(time_val.total_seconds())
                    hours, remainder = divmod(seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    time_slots.append(f"{hours:02d}:{minutes:02d}")
                elif hasattr(time_val, 'strftime'): # datetime.time
                    time_slots.append(time_val.strftime('%H:%M'))
                else: # string
                    time_slots.append(str(time_val))

        time_info = ", ".join(time_slots) if time_slots else "未設定"
        
        edit_liff_url = f"https://liff.line.me/{liff_manual_reminder_id}?mode=edit&reminder_id={r['id']}"
        
        bubble = BubbleContainer(
            body=BoxComponent(layout='vertical', padding_all='16px', spacing='md', contents=[
                TextComponent(text=r.get('drug_name', '未設定藥名'), weight='bold', size='xl'),
                SeparatorComponent(margin='md'),
                BoxComponent(layout='baseline', spacing='sm', margin='md', contents=[
                    TextComponent(text='時間', color='#aaaaaa', size='sm', flex=2),
                    TextComponent(text=time_info, color='#666666', size='sm', flex=5, wrap=True)
                ]),
                BoxComponent(layout='baseline', spacing='sm', contents=[
                    TextComponent(text='劑量', color='#aaaaaa', size='sm', flex=2),
                    TextComponent(text=r.get('dose_quantity') or '未設定', color='#666666', size='sm', flex=5, wrap=True)
                ]),
                BoxComponent(layout='baseline', spacing='sm', contents=[
                    TextComponent(text='備註', color='#aaaaaa', size='sm', flex=2),
                    TextComponent(text=r.get('notes') or '無', color='#666666', size='sm', flex=5, wrap=True)
                ]),
            ]),
            footer=BoxComponent(layout='horizontal', spacing='sm', padding_all='8px', contents=[
                ButtonComponent(action=URIAction(label='編輯', uri=edit_liff_url), style='primary', color='#3B82F6', flex=1),
                ButtonComponent(action=PostbackAction(label='刪除', data=f"action=confirm_delete_reminder&reminder_id={r['id']}"), style='secondary', color='#EF4444', flex=1)
            ])
        )
        bubbles.append(bubble)
    
    return FlexSendMessage(alt_text=f"{member['member']} 的用藥提醒", contents=CarouselContainer(contents=bubbles))


def create_reminder_options_menu(member: dict):
    """【樣式復刻】產生提醒選項選單"""
    liff_manual_id = current_app.config['LIFF_ID_MANUAL_REMINDER']
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical', padding_all='20px', spacing='lg',
            contents=[
                TextComponent(text=f'為「{member["member"]}」設定提醒', weight='bold', size='xl', color='#1F2937', align='center'),
                TextComponent(text='請選擇要進行的操作：', size='md', color='#64748B', align='center', margin='md'),
                SeparatorComponent(margin='lg'),
                BoxComponent(layout='vertical', spacing='md', margin='lg', contents=[
                    ButtonComponent(
                        action=PostbackAction(label='📋 查看現有提醒', data=f'action=view_existing_reminders&member={quote(member["member"])}'),
                        style='primary', color='#3B82F6'
                    ),
                    ButtonComponent(
                        action=PostbackAction(label='💊 從藥歷新增提醒', data=f'action=add_from_prescription&member={quote(member["member"])}'),
                        style='secondary'
                    ),
                    ButtonComponent(
                        action=URIAction(label='✏️ 手動新增提醒', uri=f"https://liff.line.me/{liff_manual_id}?mode=add&member_id={member['id']}"),
                        style='primary', color='#10B981'
                    )
                ])
            ]
        )
    )
    return FlexSendMessage(alt_text=f"為 {member['member']} 設定提醒", contents=bubble)

def create_prescription_records_carousel(member_name: str, records: list):
    """【樣式復刻】產生該成員的藥歷記錄輪播，供選擇設定提醒"""
    if not records:
        return FlexSendMessage(alt_text=f"{member_name} 沒有藥歷記錄", contents=BubbleContainer(
            body=BoxComponent(layout='vertical', spacing='md', padding_all='20px', contents=[
                TextComponent(text=f"「{member_name}」沒有藥歷記錄", weight='bold', size='lg'),
                TextComponent(text='請先掃描藥單建立藥歷，或選擇手動新增提醒。', wrap=True, size='sm', color='#64748B', margin='md'),
            ])
        ))

    bubbles = []
    liff_id = current_app.config['LIFF_ID_PRESCRIPTION_REMINDER']
    for record in records:
        visit_date = record.get('visit_date')
        if visit_date and hasattr(visit_date, 'strftime'): 
            visit_date = visit_date.strftime('%Y-%m-%d')
        elif visit_date:
            visit_date = str(visit_date)
        else:
            visit_date = '未知日期'
        
        bubble = BubbleContainer(
            body=BoxComponent(layout='vertical', spacing='md', padding_all='16px', contents=[
                TextComponent(text=f"📅 {visit_date or '未知日期'}", weight='bold', size='lg', color='#1F2937'),
                SeparatorComponent(margin='sm'),
                BoxComponent(layout='baseline', spacing='sm', margin='md', contents=[
                    TextComponent(text='診所', color='#64748B', size='sm', flex=2),
                    TextComponent(text=record.get('clinic_name') or '未知診所', color='#374151', size='sm', flex=5, wrap=True)
                ]),
                BoxComponent(layout='baseline', spacing='sm', contents=[
                    TextComponent(text='醫師', color='#64748B', size='sm', flex=2),
                    TextComponent(text=record.get('doctor_name') or '未知醫師', color='#374151', size='sm', flex=5, wrap=True)
                ]),
            ]),
            footer=BoxComponent(layout='vertical', contents=[
                ButtonComponent(
                    action=URIAction(label='設定此藥歷的提醒', uri=f"https://liff.line.me/{liff_id}?mm_id={record['mm_id']}"),
                    style='primary', color='#10B981'
                )
            ])
        )
        bubbles.append(bubble)
    
    return FlexSendMessage(alt_text=f"{member_name} 的藥歷記錄", contents=CarouselContainer(contents=bubbles))