from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta

class FormationRegistration(models.Model):
    _name = 'formation.registration'
    _inherit = ['mail.thread', 'mail.activity.mixin'] # Pour activer les notifications/chatter
    _description = 'Inscription'

    session_id = fields.Many2one('formation.session', string="Session", required=True)
    # Champ lié pour récupérer la date de fin de la session
    session_end_date = fields.Date(related='session_id.date_end', string="Date Fin Session")
    
    partner_id = fields.Many2one('res.partner', string="Participant", domain=[('is_student', '=', True)], required=True)
    project_theme = fields.Char("Thème du projet")
    project_link = fields.Char("Lien du projet")
    submission_date = fields.Date("Date de soumission")
    evaluation = fields.Float("Évaluation")
    
    status = fields.Selection([
        ('registered', 'Inscrit'),
        ('completed', 'Terminé'), # Nouvelle option
        ('cancelled', 'Annulé')
    ], string="Statut Inscription", default='registered', compute='_compute_status', store=True)

    absence_count = fields.Integer(
        string="Nombre d'absences", 
         
        help="Calculé automatiquement depuis les feuilles de présence"
    )
    
    proposed_cancellation = fields.Boolean(
        string="Proposition d'annulation", 
        compute='_compute_absence_count',
    
        help="Coché automatiquement si l'étudiant dépasse 5 absences"
    )

    # Une seule fonction pour calculer les deux champs dynamiquement
    def _compute_absence_count(self):
        for record in self:
            if record.partner_id and record.session_id:
                absences = self.env['formation.attendance'].search_count([
                    ('partner_id', '=', record.partner_id.id),
                    ('seance_id.session_id', '=', record.session_id.id),
                    ('attendance_status', '=', 'absent')
                ])
                record.absence_count = absences
                record.proposed_cancellation = absences > 5
            else:
                record.absence_count = 0
                record.proposed_cancellation = False  

    def _notify_admin_absences(self):
        """ Envoie une notification interne et crée une activité pour l'admin """
        for record in self:
            # 1. Poster un message dans le chatter
            body = _("ATTENTION : L'étudiant %s a atteint %s absences. Une annulation d'inscription est préconisée.") % (
                record.partner_id.name, record.absence_count
            )
            record.message_post(body=body, message_type='notification', subtype_xmlid='mail.mt_note')

            # 2. Créer une activité (Tâche) pour l'administrateur
            self.env['mail.activity'].create({
                'res_id': record.id,
                'res_model_id': self.env['ir.model']._get(record._name).id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': "Vérification pour annulation d'inscription",
                'note': body,
                'user_id': self.env.user.id, # Ou l'ID de l'admin spécifique
            })

    def action_confirm_cancellation(self):
        """ Bouton pour que l'admin valide l'annulation proposée """
        self.write({'status': 'cancelled', 'proposed_cancellation': False})
         # On ajoute un message dans le chatter pour garder une trace de l'action manuelle
        self.message_post(body=_("L'inscription a été annulée suite à un dépassement du nombre d'absences autorisé."))


   # pour confirmation et cloture de formation automatique ou annulation automatique 
    @api.depends('submission_date', 'project_link', 'session_id.date_end')
    def _compute_status(self):
        today = fields.Date.today()
        for record in self:
            if not record.session_id or not record.session_id.date_end:
                continue
                
            limit_date = record.session_id.date_end + timedelta(days=15)

            # Règle 1 : Annulation si absence de projet après 15 jours
            if not record.project_link and not record.submission_date:
                if today > limit_date:
                    record.status = 'cancelled'
                    continue

            # Règle 2 : Terminé si projet soumis dans les délais
            if record.status == 'registered' and record.submission_date:
                if record.submission_date <= limit_date:
                    record.status = 'completed'

  #evaluation comprise entre 0 et 20
    @api.constrains('evaluation')
    def _check_grade_range(self):
        for record in self:
            if record.evaluation < 0 or record.evaluation> 20:
                raise ValidationError("La note d'évaluation doit impérativement être comprise entre 0 et 20.")
                
                    