{
    'name': 'Gestion de Formation CETIC',
    'version': '1.0',
    'category': 'Education',
    'summary': 'Gestion des sessions, participants et présences',
    'depends': ['base','mail'], # TRÈS IMPORTANT pour res.partner
    'data': [
        'security/ir.model.access.csv',  # Toujours la sécurité en premier !
        'views/formation_views.xml',
        'views/session_views.xml',
        'views/room_views.xml',
        'views/seance_views.xml',
        'views/formation_dashboard_views.xml',
        'views/attendance_views.xml',
        'views/registration_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
}