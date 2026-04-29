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

    # Calcul automatique de la note selon le taux de présence
    evaluation = fields.Float("Taux d'assistance", compute="_compute_attendance_rate")

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
    # Action pour le bouton PDF                
    def action_print_certificate(self):
            """ 
            Cette fonction déclenche l'impression du PDF. 
            self.env.ref(...) cherche l'ID de l'action définie dans le XML.
            """
            # On s'assure que l'enregistrement est bien chargé
            self.ensure_one()
            
            # On appelle l'action du rapport définie en XML
            return self.env.ref('gestion_formation.action_report_attestation').report_action(self)                   



    # Voir les présences d'un participant spécifique
    def action_view_attendance(self):
        return {
            'name': f'Présences de {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'formation.attendance',
            'view_mode': 'tree',
            'domain': [('partner_id', '=', self.partner_id.id), ('seance_id.session_id', '=', self.session_id.id)],
            'target': 'new',
        }
    

    @api.depends('session_id.seance_ids', 'session_id.duration_total')
    def _compute_attendance_rate(self):
        for reg in self:
            total_h = reg.session_id.duration_total
            if total_h <= 0:
                reg.evaluation = 0
                continue
            # Somme des heures des séances où l'élève était présent
            present_h = sum(self.env['formation.attendance'].search([
                ('partner_id', '=', reg.partner_id.id),
                ('seance_id.session_id', '=', reg.session_id.id),
                ('attendance_status', '=', 'present')
            ]).mapped('seance_id.duration'))
            reg.evaluation = (present_h / total_h) * 100



    
  
    
    @api.model_create_multi
    def create(self, vals_list):
        # 1. Création standard de l'inscription
        registrations = super(FormationRegistration, self).create(vals_list)
        
        for reg in registrations:
            # 2. On récupère toutes les séances déjà existantes pour cette session
            seances = reg.session_id.seance_ids
            
            # 3. Pour chaque séance, on crée une ligne de présence "Brouillon" pour ce participant
            for seance in seances:
                self.env['formation.attendance'].create({
                    'seance_id': seance.id,
                    'partner_id': reg.partner_id.id,
                    'attendance_status': '',
                })
        return registrations
    
    def unlink(self):
        for reg in self:
            # Supprimer les présences liées à ce participant pour cette session spécifique
            self.env['formation.attendance'].search([
                ('partner_id', '=', reg.partner_id.id),
                ('seance_id.session_id', '=', reg.session_id.id)
            ]).unlink()
        return super(FormationRegistration, self).unlink()