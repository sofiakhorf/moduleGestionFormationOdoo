
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