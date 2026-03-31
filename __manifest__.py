{
    'name': 'Gestion de Formation CETIC',
    'version': '1.0',
    'category': 'Education',
    'summary': 'Gestion des sessions, participants et présences',
    'depends': ['base'], # TRÈS IMPORTANT pour res.partner
    'data': [
        'security/ir.model.access.csv',  # Toujours la sécurité en premier !
        'views/formation_views.xml',
    ],
    'installable': True,
    'application': True,
}