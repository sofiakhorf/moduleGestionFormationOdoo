
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FormationSeance(models.Model):
    _name = 'formation.seance'
    _description = 'Séance'
 
    date_day = fields.Date("Date du jour", required=True)
    start_hour = fields.Float("Heure Début", required=True)
    end_hour = fields.Float("Heure Fin", required=True)
    
    # Relation 1,1 (Association 'composer')
    session_id = fields.Many2one('formation.session', string="Session", required=True)
    room_id = fields.Many2one('formation.room', string="Salle", required=True)
    # PERMET DE FAIRE L'APPEL DEPUIS LA SÉANCE
    attendance_ids = fields.One2many('formation.attendance', 'seance_id', string="Feuille d'appel")

    duration = fields.Float(
        string="Durée (Heures)", 
        compute="_compute_duration", 
        store=True, 
        help="Calculé automatiquement : Heure de fin - Heure de début"
    )
       # 1. Calcul de l'occupation par séance
    occupation_percent = fields.Integer(
        string="Présents", 
        compute="_occupation_percent_count", 
        store=True
    )
    # . Le champ technique qui va stocker les salles occupées
    unavailable_room_ids = fields.Many2many(
        'formation.room',
        compute='_compute_unavailable_rooms'
    )

    # 2. La fonction de calcul (qui remplace le onchange)
    @api.depends('date_day', 'start_hour', 'end_hour')
    def _compute_unavailable_rooms(self):
        for record in self:
            if record.date_day and record.start_hour and record.end_hour:
                # On utilise l'ID d'origine si on est en train de créer un nouvel enregistrement
                current_id = record._origin.id if record._origin else False
                
               
                overlapping = self.env['formation.seance'].search([
                    ('id', '!=', current_id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour),
                    ('session_id.state', 'in', ['confirmed', 'in_progress']) # Logique métier respectée
                ])
                record.unavailable_room_ids = overlapping.mapped('room_id')
            else:
                record.unavailable_room_ids = False


    @api.depends('attendance_ids.attendance_status')
    def _occupation_percent_count(self):
        for record in self:
            # On compte uniquement ceux marqués 'present'
            present_count = len(record.attendance_ids.filtered(lambda a: a.attendance_status == 'present'))
            # Calcul du pourcentage par rapport à la capacité de la salle
            if record.session_id and record.session_id.seats > 0:
                record.occupation_percent = (present_count / record.session_id.seats) * 100
            else:
                record.occupation_percent = 0.0

    @api.onchange('date_day', 'start_hour', 'end_hour')
    def _onchange_seance_times(self):
        # 1. Préparation du dictionnaire de réponse
        res = {'domain': {}} 
        
        if self.date_day and self.start_hour and self.end_hour:
            # 2. Ton calcul pour trouver les IDs des salles occupées
            unavailable_rooms = self.env['formation.seance'].search([
                ('id', '!=', self._origin.id if self._origin else False),
                ('date_day', '=', self.date_day),
                ('start_hour', '<', self.end_hour),
                ('end_hour', '>', self.start_hour),
            ]).mapped('room_id').ids
            
            # 3. L'INSTRUCTION : On dit à Odoo d'appliquer ce filtre au champ 'room_id'
            res['domain'] = {
                'room_id': [
                    ('id', 'not in', unavailable_rooms), 
                    
                ]
            }
        
        # 4. LE RETOUR : Odoo reçoit 'res' et met à jour l'interface automatiquement
        return res

    @api.depends('start_hour', 'end_hour')
    def _compute_duration(self):
        for record in self:
            if record.start_hour and record.end_hour:
                # Calcul simple car les heures sont des Float (ex: 14.5 pour 14h30)
                diff = record.end_hour - record.start_hour
                # On s'assure que la durée n'est pas négative
                record.duration = diff if diff > 0 else 0.0
            else:
                record.duration = 0.0
    # 1. Contrainte de cohérence des dates
    @api.constrains('start_hour', 'end_hour')
    def _check_dates(self):
        for record in self:
            # Correction : on compare end_hour avec start_hour
            if record.start_hour and record.end_hour :
                 if  record.end_hour < record.start_hour:
                   raise ValidationError("L'heure de fin ne peut pas être antérieure à l'heure de début !")
                 duration = record.end_hour - record.start_hour
                 if duration > 12:
                   raise ValidationError("Une séance ne peut pas durer plus de 12 heures !")
       
                 if record.start_hour == record.end_hour:
                     raise ValidationError("L'heure de début et de fin ne peuvent pas être identiques.")
                 
    
# 2. API  : Éviter que deux seance occupent la même salle aux mêmes dates et que la salle choisi soit en maintenance 
    @api.constrains('date_day', 'start_hour', 'end_hour', 'room_id')
    def _check_room_availability_and_state(self):
        for record in self:
            if not record.room_id:
                continue
                
            # 1. Vérification du statut "En Travaux"
            if record.room_id.state == 'maintenance':
                raise ValidationError(
                    f"Impossible de réserver : La salle '{record.room_id.name}' "
                    f"est actuellement en travaux ou en maintenance."
                )

            # 2. Vérification des conflits de dates (Chevauchement)
            if record.start_hour and record.end_hour:
                overlapping_seance = self.search([
                        ('id', '!=', record.id),
                        ('room_id', '=', record.room_id.id),
                        ('date_day', '=', record.date_day),
                        ('start_hour', '<', record.end_hour),
                        ('end_hour', '>', record.start_hour),
                        # IMPORTANT : On ne regarde les conflits qu'avec d'autres sessions ACTIVES
                        ('session_id.state', 'in', ['confirmed', 'in_progress']),
                        ])
                if overlapping_seance:
                  raise ValidationError(f"La salle {record.room_id.name} est déjà occupée le {record.date_day} "
                    f"entre {overlapping_seance[0].start_hour}h et {overlapping_seance[0].end_hour}h !"
                     )
                
       
# 3. Vérification de la capacité 
    @api.constrains('room_id', 'session_id')
    def _check_room_capacity(self):
        for record in self:
            if record.room_id and record.session_id:
                # On récupère le nombre RÉEL d'inscrits via la relation
                participants_count = len(record.session_id.registration_ids)
                room_capacity = record.room_id.capacity
                
                if participants_count > room_capacity:
                    raise ValidationError(
                        f"Capacité de salle insuffisante ! La session '{record.session_id.name}' "
                        f"compte actuellement {participants_count} inscrits, mais la salle '{record.room_id.name}' "
                        f"ne peut en accueillir que {room_capacity}."
                    )

# 4. API : Vérifier que la date de la séance est dans les limites de la session
    @api.constrains('date_day', 'session_id')
    def _check_date_within_session(self):
        for record in self:
            # On s'assure que la séance a une date et qu'elle est bien reliée à une session
            if record.date_day and record.session_id:
                session = record.session_id
                
                # Vérification par rapport à la date de début de la session
                if session.date_start and record.date_day < session.date_start:
                    raise ValidationError(
                        f"Erreur de date : La séance est prévue le {record.date_day}, "
                        f"mais la session '{session.name}' ne commence que le {session.date_start}."
                    )
                
                # Vérification par rapport à la date de fin de la session
                if session.date_end and record.date_day > session.date_end:
                    raise ValidationError(
                        f"Erreur de date : La séance est prévue le {record.date_day}, "
                        f"mais la session '{session.name}' se termine le {session.date_end}."
                    )     






    # 5.  Bloquer les séances si session Annulée ou Reportée
    @api.constrains('session_id')
    def _check_session_status_for_seance(self):
        """
        Empêche de créer ou modifier une séance si la session associée n'est pas active.
        """
        for record in self:
            if record.session_id and record.session_id.state in ['cancelled', 'postponed']:
                raise ValidationError(
                    f"Action interdite : Vous ne pouvez pas planifier ou modifier une séance "
                    f"car la session '{record.session_id.name}' est actuellement "
                    f"{dict(record.session_id._fields['state'].selection).get(record.session_id.state)}."
                ) 
                            
    
    #Cette règle interdit à une session d'occuper deux salles en même temps le même jour avec chevauchement de temps 

    @api.constrains('date_day', 'start_hour', 'end_hour', 'session_id')
    def _check_session_overlap(self):
        for record in self:
            if record.session_id and record.date_day:
                overlap = self.search([
                    ('id', '!=', record.id),
                    ('session_id', '=', record.session_id.id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour)
                ])
                if overlap:
                    raise ValidationError(
                        f"Conflit de session : Les séances d'une même session ne peuvent pas se chevaucher. "
                        f"Il y a déjà une séance prévue de {overlap[0].start_hour}h à {overlap[0].end_hour}h."
                    )
                
  # empeche que le meme instructeur supervise une autre session le meme jour avec des horaires qui se chevauche 
    @api.constrains('date_day', 'start_hour', 'end_hour', 'session_id')
    def _check_instructor_double_booking(self):
        """ 
        Empêche un formateur de donner deux séances différentes 
        au même moment le même jour.
        """
        for record in self:
            if record.start_hour and record.end_hour and record.session_id and record.session_id.instructor_id:
                
                # On récupère l'ID du formateur assigné à la session de cette séance
                current_instructor = record.session_id.instructor_id.id
                
                # On cherche si ce formateur est déjà occupé ailleurs
                overlapping_seance = self.search([
                    ('id', '!=', record.id),
                    ('date_day', '=', record.date_day),
                    ('start_hour', '<', record.end_hour),
                    ('end_hour', '>', record.start_hour),
                    # On cible les séances dont la session appartient au même formateur
                    ('session_id.instructor_id', '=', current_instructor),
                    # On ignore les sessions annulées
                    ('session_id.state', 'not in', ['cancelled', 'draft'])
                ])
                
                if overlapping_seance:
                    raise ValidationError(
                        f"Conflit d'emploi du temps ! Le formateur '{record.session_id.instructor_id.name}' "
                        f"ne peut pas assurer cette séance. Il anime déjà la session "
                        f"'{overlapping_seance[0].session_id.name}' le {record.date_day} "
                        f"entre {overlapping_seance[0].start_hour}h et {overlapping_seance[0].end_hour}h."
                    )
                


    @api.model_create_multi
    def create(self, vals_list):
        # 1. Création de la séance
        seances = super(FormationSeance, self).create(vals_list)
        
        for seance in seances:
            # 2. On récupère les participants déjà inscrits à la session parente
            participants = seance.session_id.registration_ids
            
            # 3. On crée automatiquement leur ligne de présence pour cette nouvelle séance
            for reg in participants:
                self.env['formation.attendance'].create({
                    'seance_id': seance.id,
                    'partner_id': reg.partner_id.id,
                })
        return seances