from odoo import models

class FormationNotificationMixin(models.AbstractModel):
    _name = 'formation.notification.mixin'
    _description = "Mixin pour les alertes admin du module Formation"
    _inherit = ['mail.thread', 'mail.activity.mixin'] 
    
    def notify_admin(self, note, summary="Alerte Formation"):
        """ Poste un message dans le chatter + crée une tâche pour l'admin """
        for record in self:
            record.message_post(
                body=f"<b>ALERTE :</b> {note}",
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                note=note,
                user_id=self.env.user.id,
                summary=summary
            )