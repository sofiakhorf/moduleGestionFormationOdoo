from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta

class FormationRegistration(models.Model):
    _name = 'formation.registration'
    _inherit = [ 'formation.notification.mixin']
    _description = 'Inscription'

    # =========================================================================
    # 1. CHAMPS & RELATIONS
    # =========================================================================
    session_id = fields.Many2one('formation.session', string="Session", required=True)
    session_end_date = fields.Date(related='session_id.date_end', string="Date Fin Session")
    partner_id = fields.Many2one('res.partner', string="Participant", domain=[('is_student', '=', True)], required=True)
    
    project_theme = fields.Char("Thème du projet")
    project_link = fields.Char("Lien du projet")
    submission_date = fields.Date("Date de soumission")
    
    status = fields.Selection([
        ('registered', 'Inscrit'),
        ('completed', 'Terminé'),
        ('cancelled', 'Annulé')
    ], string="Statut Inscription", default='registered', compute='_compute_status', store=True)


    attendance_ids = fields.One2many(
    'formation.attendance', 
    'registration_id', 
    string="Feuilles de présence"
    )

    absence_count = fields.Integer(
        string="Nombre d'absences", store=True,
        compute='_compute_absence_count',
        help="Calculé automatiquement depuis les feuilles de présence"
    )
    
    proposed_cancellation = fields.Boolean(
        string="Proposition d'annulation", 
        compute='_compute_absence_count',  store=True, 
        help="Coché automatiquement si l'étudiant dépasse 5 absences"
    )

    evaluation = fields.Float("Taux d'assistance", compute="_compute_attendance_rate")

    # =========================================================================
    # 2. MÉTHODES CALCULÉES (@api.depends)
    # =========================================================================
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

    @api.depends('session_id.seance_ids', 'session_id.duration_total', 'attendance_ids.attendance_status', 'attendance_ids.seance_id.duration')
    def _compute_attendance_rate(self):
        for reg in self:
            total_h = reg.session_id.duration_total
            if total_h <= 0:
                reg.evaluation = 0
                continue
                
            # ✅ Exploitation directe du champ relationnel (utilise le cache et fonctionne sans sauvegarde)
            present_attendances = reg.attendance_ids.filtered(lambda a: a.attendance_status == 'present')
            present_h = sum(present_attendances.mapped('seance_id.duration'))
            
            reg.evaluation = (present_h / total_h) * 100
    @api.depends('attendance_ids.attendance_status')
    def _compute_absence_count(self):
        """ Purement calculatoire : aucun effet de bord, donc sans risque
        même déclenché par un onchange en formulaire non sauvegardé. """
        for record in self:
            absences = len(record.attendance_ids.filtered(lambda a: a.attendance_status == 'absent'))
            record.absence_count = absences
            record.proposed_cancellation = absences > 5

    # =========================================================================
    # 3. CONTRAINTES DE VALIDATION (@api.constrains)
    # =========================================================================
    @api.constrains('evaluation')
    def _check_grade_range(self):
        for record in self:
            if record.evaluation < 0 or record.evaluation > 100:
                raise ValidationError("Le taux d'assistance doit être compris entre 0 et 100.")

    # =========================================================================
    # 4. ACTIONS BOUTONS ET MÉTHODES MÉTIER
    # =========================================================================

    def _notify_if_absence_threshold_crossed(self, previous_state=None):
            """ Compare l'état avant/après une sauvegarde réelle de présence,
            et notifie l'admin uniquement au franchissement du seuil. """
            for record in self:
                was_proposed = previous_state.get(record.id, False) if previous_state else False
                if record.proposed_cancellation and not was_proposed:
                    record.notify_admin(
                        f"L'étudiant {record.partner_id.name} a atteint {record.absence_count} absences.",
                        summary="Vérification pour annulation d'inscription"
                    )
    def action_confirm_cancellation(self):
        """ Bouton pour que l'admin valide l'annulation proposée """
        self.write({'status': 'cancelled', 'proposed_cancellation': False})
        self.message_post(body=_("L'inscription a été annulée suite à un dépassement du nombre d'absences autorisé."))

    def action_print_certificate(self):
        """ Déclenche l'impression du rapport PDF d'attestation """
        self.ensure_one()
        return self.env.ref('module_gestion_formation_odoo.action_report_attestation').report_action(self)

    def action_view_attendance(self):
        """ Affichage de la liste des présences du participant """
        return {
            'name': f'Présences de {self.partner_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'formation.attendance',
            'view_mode': 'tree',
            'domain': [('registration_id', '=', self.id)],
            'target': 'new',
        }

    # =========================================================================
    # 5. SURCHARGE DES MÉTHODES ORM (CRUD)
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        registrations = super(FormationRegistration, self).create(vals_list)
        attendance_vals = []
        
        for reg in registrations:
            for seance in reg.session_id.seance_ids:
                attendance_vals.append({
                    'seance_id': seance.id,
                    'registration_id': reg.id,
                    'attendance_status': 'present' #  Initialisation explicite de l'état
                })
                
        #  Création en masse (1 seule requête SQL au lieu d'une par séance)
        if attendance_vals:
            self.env['formation.attendance'].create(attendance_vals)
            
        return registrations
    
    