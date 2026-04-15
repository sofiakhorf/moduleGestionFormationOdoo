from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
import pytz

class FormationRoom(models.Model):
    _name = 'formation.room'
    _description = 'Salle de Formation'

    name = fields.Char(string="Nom de la salle", required=True)
    capacity = fields.Integer(string="Capacité (Places)", required=True)
    location = fields.Char(string="Emplacement / Bâtiment")


    state = fields.Selection([
        ('available', 'Disponible'),
        ('occupied', 'Occupée'),
        ('maintenance', 'En Travaux / Maintenance'),
        ('archived', 'Désactivée')
    ], string="Statut de la salle", default='available', required=True)
    
    # Relation pour voir quelles sessions occupent cette salle
    seance_ids = fields.One2many('formation.seance', 'room_id', string="Séances programmées")
    
    seances_count = fields.Integer(
        string="Nombre de Sessions", 
        compute="_compute_seances_count", 
        store=True
    )

    @api.depends('seance_ids')
    def _compute_seances_count(self):
        for room in self:
            room.seances_count = len(room.seance_ids)

    @api.constrains('capacity')
    def _check_capacity_positive(self):
        for record in self:
            if record.capacity <= 0:
                raise ValidationError("La capacité de la salle doit être supérieure à zéro.")
            
    # 2. Validation pour Désactiver ou Maintenance
    @api.constrains('state')
    def _check_state_change_rules(self):
        for room in self:
            if room.state in ['maintenance', 'archived']:
                # Chercher une séance aujourd'hui ou dans le futur (non annulée)
                active_seances = self.env['formation.seance'].search([
                    ('room_id', '=', room.id),
                    ('date_day', '>=', fields.Date.today()),
                    ('session_id.state', 'not in', ['cancelled'])
                ])
                if active_seances:
                    # Message spécifique selon l'état
                    action = "désactiver" if room.state == 'archived' else "mettre en maintenance"
                    raise ValidationError(
                        f"Impossible de {action} la salle '{room.name}'. "
                        f"Il y a {len(active_seances)} séance(s) programmée(s) actuellement."
                    )


    # 3. Méthode pour le changement automatique (À appeler via une action planifiée - CRON)
    @api.model
    def _update_room_availability(self):
        """ Vérifie l'heure actuelle et bascule la salle en 'Occupée' ou 'Disponible' """
        user_tz = self.env.user.tz or 'Africa/Algiers'
        local_tz = pytz.timezone(user_tz)
        now = datetime.now(local_tz)
        
        current_date = now.date()
        # Conversion de l'heure actuelle en format float (ex: 14h30 -> 14.5)
        current_hour_float = now.hour + (now.minute / 60.0)

        # On ne vérifie que les salles disponibles ou occupées
        rooms = self.search([('state', 'in', ['available', 'occupied'])])
        
        for room in rooms:
            # Chercher une séance EN CE MOMENT dans cette salle
            ongoing_seance = self.env['formation.seance'].search([
                ('room_id', '=', room.id),
                ('date_day', '=', current_date),
                ('start_hour', '<=', current_hour_float),
                ('end_hour', '>', current_hour_float),
                ('session_id.state',  'in' ,['confirmed', 'in_progress'])
            ], limit=1)



            target_state = 'occupied' if ongoing_seance else 'available'
            
            # On utilise with_context pour bypasser la protection de la méthode write
            if room.state != target_state:
                room.with_context(auto_status_update=True).write({'state': target_state})



    #  Protection contre les changements manuels interdits
    def write(self, vals):
        # On autorise le changement automatique si on passe par le CRON (via le contexte)
        if not self.env.context.get('auto_status_update'):
            for record in self:
                if 'state' in vals:
                    new_state = vals['state']
                    
                    # 1. Bloquer TOUJOURS le passage manuel vers 'Occupée'
                    if new_state == 'occupied' and record.state != 'occupied':
                        raise ValidationError(
                            "Le statut 'Occupée' est géré automatiquement par le système selon le planning."
                        )
                    
                    # 2. Interdire de repasser de 'Occupée' à 'Disponible' si une séance tourne
                    if record.state == 'occupied' and new_state == 'available':
                        raise ValidationError("La salle est actuellement utilisée par une séance. Attendez la fin ")
                    
                    # 2. Interdire de repasser de 'Disponible' à 'occupé' si une séance tourne
                    if record.state == 'available' and new_state == 'occupied':
                        raise ValidationError("une salle sera occupé uniquement quand vous ajouter une seance dans les horaires actuelle ")
                    

                            
               
        return super(FormationRoom, self).write(vals)
