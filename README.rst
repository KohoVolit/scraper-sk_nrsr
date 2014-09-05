===============
sk_nrsr_scraper
===============

Scraper of Slovak National Council for `Visegrad+ project`_.

.. _`Visegrad+ project`: http://www.parldata.eu

.. contents:: :backlinks: none


Installation
============

Requirements
------------

Requires lxml_ package for Python. On Debian-based distributions can be installed by:

  .. code-block:: console

      $ sudo apt-get install libxml2-dev libxslt-dev zlib1g-dev python3-pip
      $ sudo pip3 install lxml

.. _lxml: http://lxml.de


Download
--------

Get scraper by:

  .. code-block:: console

      $ sudo git clone https://github.com/KohoVolit/sk_nrsr_scraper.git

and VPAPI client and SSH certificate of the server by:

  .. code-block:: console

      $ cd sk_nrsr_scraper
      $ wget https://raw.githubusercontent.com/KohoVolit/visegrad-parliament-api/master/client/vpapi.py
      $ wget https://raw.githubusercontent.com/KohoVolit/visegrad-parliament-api/master/client/server_cert_prod.pem

	  
Configuration
-------------

Check that ``SERVER_NAME`` and ``SERVER_CERT`` variables in ``vpapi.py`` have correct values.

Create environment variable with name ``VPAPI_PWD_SK_NRSR`` that contains the password for write access through API:

  .. code-block:: console

      $ export VPAPI_PWD_SK_NRSR type-password-here


Running
=======

See help message of the scraper for parameters the scraper accepts:

  .. code-block:: console

      $ python3 scrape.py --help
