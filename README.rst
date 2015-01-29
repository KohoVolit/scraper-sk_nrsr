===============
scraper-sk_nrsr
===============

Scraper of Slovak National Council for `Visegrad+ project`_. Scrapes MPs, their memberships, votes and debates and stores the data into `Visegrad+ parliament API`_.

.. _`Visegrad+ project`: http://www.parldata.eu
.. _`Visegrad+ parliament API`: https://github.com/KohoVolit/api.parldata.eu

.. contents:: :backlinks: none


Installation
============

Prerequisites
-------------

Requires:

* lxml_ library to parse HTML documents,
* LibreOffice_ core and unoconv_ to convert documents from RTF format,
* some Python packages.

.. _lxml: http://lxml.de
.. _LibreOffice: http://www.libreoffice.org/
.. _unoconv: http://dag.wiee.rs/home-made/unoconv/

On Debian-based distributions install the libraries:

  .. code-block:: console

      $ sudo apt-get install libxml2-dev libxslt1-dev zlib1g-dev libreoffice-core unoconv


Download
--------

Get the scraper:

  .. code-block:: console

      $ sudo mkdir --p /home/projects/scrapers
      $ cd /home/projects/scrapers
      $ sudo git clone https://github.com/KohoVolit/scraper-sk_nrsr.git sk_nrsr

Get VPAPI client and SSH certificate of the server:

  .. code-block:: console

      $ cd sk_nrsr
      $ sudo wget https://raw.githubusercontent.com/KohoVolit/api.parldata.eu/master/client/vpapi.py
      $ sudo wget https://raw.githubusercontent.com/KohoVolit/api.parldata.eu/master/client/server_cert.pem

Create a virtual environment for the scraper and install the required packages into it:

  .. code-block:: console

      $ sudo virtualenv /home/projects/.virtualenvs/scrapers/sk_nrsr --no-site-packages
      $ source /home/projects/.virtualenvs/scrapers/sk_nrsr/bin/activate
      (sk_nrsr)$ sudo pip install -r requirements.txt
      (sk_nrsr)$ deactivate


Configuration
-------------

Check that ``SERVER_NAME`` and ``SERVER_CERT`` variables in ``vpapi.py`` have correct values.

Copy file ``conf/private-example.json`` to ``conf/private.json`` and fill in your username and password for write access through API. Those sensitive data *must not* be present in the repository.


Running
=======

Run in the virtual environment. See help message of the scraper for parameters the scraper accepts

  .. code-block:: console

      $ source /home/projects/.virtualenvs/scrapers/sk_nrsr/bin/activate
      $ python scrape.py --help

``unoconv`` listener must be running to scrape transcripts of former debates (election terms 1-4)

  .. code-block:: console

      $ unoconv --listener

Scrape people and their memberships first, then debates and finally votes (initial scrape of debates deletes all existing sessions and sittings)

  .. code-block:: console

      $ python scrape.py --people initial --debates none --votes none
      $ python scrape.py --people none --debates initial --votes none
      $ python scrape.py --people none --debates none --votes initial

or all at once

  .. code-block:: console

      $ python scrape.py --people initial --debates initial --votes initial

You can stop unoconv listener unless needed for other scrapers or conversions

      $ killall soffice.bin

Then schedule periodic scrape

  .. code-block:: console

      $ python scrape.py --people recent --debates recent --votes recent

or, knowing that ``recent`` is the default value, simply

  .. code-block:: console

      $ python scrape.py
