{
    'name': 'Gestion de Formation CETIC',
    'version': '1.0',
    'category': 'Education',
    'summary': 'Gestion des sessions, participants et présences',
    'depends': ['base'], # TRÈS IMPORTANT pour res.partner
    'data': [
        'views/formation_views.xml',
    ],
    'installable': True,
    'application': True,
}