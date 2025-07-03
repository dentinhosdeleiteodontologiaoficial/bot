# src/routes/whatsapp.py

from flask import Blueprint, request, jsonify
from src.models.conversation import db, Conversation, Appointment
# Importa a sua classe BotLogic e o serviço de envio
from src.services.bot_logic import BotLogic
from src.services.whatsapp_service import send_whatsapp_message
import json
import os

whatsapp_bp = Blueprint('whatsapp', __name__)
# Cria uma única instância do BotLogic para manter os estados da conversa
bot_logic = BotLogic()

@whatsapp_bp.route('/webhook', methods=['GET'])
def verify_webhook():
    """Verificação do webhook do WhatsApp Business API"""
    verify_token = os.environ.get('VERIFY_TOKEN', 'DENTINHOS_VERIFY_TOKEN')
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token and mode == 'subscribe' and token == verify_token:
        print("Webhook verificado com sucesso!")
        return challenge
    else:
        print("Falha na verificação do Webhook.")
        return "Token de verificação inválido", 403

@whatsapp_bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """Processa mensagens recebidas do WhatsApp"""
    try:
        data = request.get_json()
        if data and 'entry' in data:
            for entry in data['entry']:
                for change in entry.get('changes', []):
                    if change.get('field') == 'messages':
                        process_message(change['value'])
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Erro ao processar webhook: {str(e)}")
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500

def process_message(message_data):
    """Extrai a mensagem e chama a lógica do bot."""
    if 'messages' in message_data:
        for message in message_data['messages']:
            # Ignora mensagens que não são de texto (ex: status de entrega, reações)
            if message.get('type') != 'text':
                continue

            phone_number = message['from']
            message_text = message.get('text', {}).get('body', '')
            
            # Regista a mensagem recebida
            conversation = Conversation(
                phone_number=phone_number,
                message=message_text,
                message_type='incoming',
                status='received'
            )
            db.session.add(conversation)
            db.session.commit()
            
            # Usa a sua lógica para obter a resposta
            response_text = bot_logic.process_message(message_text, phone_number)
            
            if response_text:
                # Envia a resposta para o utilizador
                send_whatsapp_message(phone_number, response_text)
                
                # Atualiza o registo da conversa com a resposta enviada
                conversation.response = response_text
                conversation.status = 'processed'
                db.session.commit()

# O resto do ficheiro com as rotas de administração pode permanecer igual.
# ... (as funções get_conversations, get_appointments, etc.)
@whatsapp_bp.route('/conversations', methods=['GET'])
def get_conversations():
    conversations = Conversation.query.order_by(Conversation.timestamp.desc()).all()
    return jsonify([conv.to_dict() for conv in conversations])

@whatsapp_bp.route('/appointments', methods=['GET'])
def get_appointments():
    appointments = Appointment.query.order_by(Appointment.timestamp.desc()).all()
    return jsonify([apt.to_dict() for apt in appointments])

@whatsapp_bp.route('/appointments/<int:appointment_id>/status', methods=['PUT'])
def update_appointment_status(appointment_id):
    data = request.get_json()
    appointment = Appointment.query.get_or_404(appointment_id)
    appointment.status = data.get('status', appointment.status)
    db.session.commit()
    return jsonify(appointment.to_dict())

