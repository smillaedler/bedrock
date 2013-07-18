# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django.core import mail
from django.test.client import Client

from captcha.fields import ReCaptchaField
from funfactory.urlresolvers import reverse
from jinja2.exceptions import TemplateNotFound
from mock import Mock, patch
from nose.tools import assert_false, eq_, ok_
from pyquery import PyQuery as pq

from bedrock.mozorg.tests import TestCase
from lib import l10n_utils


class TestViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_hacks_newsletter_frames_allow(self):
        """
        Bedrock pages get the 'x-frame-options: DENY' header by default.
        The hacks newsletter page is framed, so needs to ALLOW.
        """
        with self.activate('en-US'):
            resp = self.client.get(reverse('mozorg.hacks_newsletter'))

        ok_('x-frame-options' not in resp)


class TestUniversityAmbassadors(TestCase):
    @patch.object(ReCaptchaField, 'clean', Mock())
    @patch('bedrock.mozorg.forms.request')
    @patch('bedrock.mozorg.forms.basket.subscribe')
    def test_subscribe(self, mock_subscribe, mock_request):
        mock_subscribe.return_value = {'token': 'token-example',
                                       'status': 'ok',
                                       'created': 'True'}
        c = Client()
        data = {'email': u'dude@example.com',
                'country': 'gr',
                'fmt': 'H',
                'first_name': 'foo',
                'last_name': 'bar',
                'current_status': 'teacher',
                'school': 'TuC',
                'city': 'Chania',
                'age_confirmation': 'on',
                'expected_graduation_year': '',
                'nl_about_mozilla': 'on',
                'area': '',
                'area_free_text': '',
                'privacy': 'True'}
        request_data = {'FIRST_NAME': data['first_name'],
                        'LAST_NAME': data['last_name'],
                        'STUDENTS_CURRENT_STATUS': data['current_status'],
                        'STUDENTS_SCHOOL': data['school'],
                        'STUDENTS_GRAD_YEAR': data['expected_graduation_year'],
                        'STUDENTS_MAJOR': data['area'],
                        'COUNTRY_': data['country'],
                        'STUDENTS_CITY': data['city'],
                        'STUDENTS_ALLOW_SHARE': 'N'}
        with self.activate('en-US'):
            c.post(reverse('mozorg.contribute_university_ambassadors'), data)
        mock_subscribe.assert_called_with(
            data['email'], ['ambassadors', 'about-mozilla'], format=u'H',
            country=u'gr', source_url=u'',
            welcome_message='Student_Ambassadors_Welcome')
        mock_request.assert_called_with('post',
                                        'custom_update_student_ambassadors',
                                        token='token-example',
                                        data=request_data)


@patch.object(l10n_utils, 'lang_file_is_active', lambda *x: True)
class TestContribute(TestCase):
    def setUp(self):
        self.client = Client()
        with self.activate('en-US'):
            self.url_en = reverse('mozorg.contribute')
        with self.activate('pt-BR'):
            self.url_pt_br = reverse('mozorg.contribute')
        self.contact = 'foo@bar.com'
        self.data = {
            'contribute-form': 'Y',
            'email': self.contact,
            'interest': 'coding',
            'privacy': True,
            'comments': 'Wesh!',
        }

    def tearDown(self):
        mail.outbox = []

    def test_newsletter_en_only(self):
        """Test that the newsletter features are only available in en-US"""
        response = self.client.get(self.url_en)
        doc = pq(response.content)
        ok_(doc('.field-newsletter'))
        ok_(doc('a[href="#newsletter"]'))
        ok_(doc('#newsletter'))

        with self.activate('fr'):
            url = reverse('mozorg.contribute')
        response = self.client.get(url)
        doc = pq(response.content)
        assert_false(doc('.field-NEWSLETTER'))
        assert_false(doc('a[href="#newsletter"]'))
        assert_false(doc('#newsletter'))

    @patch.object(ReCaptchaField, 'clean', Mock())
    def test_no_autoresponse(self):
        """Test contacts for functional area without autoresponses"""
        self.data.update(interest='coding')
        self.client.post(self.url_en, self.data)
        eq_(len(mail.outbox), 1)

        m = mail.outbox[0]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, ['contribute@mozilla.org'])
        eq_(m.cc, ['josh@joshmatthews.net'])
        eq_(m.extra_headers['Reply-To'], self.contact)

    @patch.object(ReCaptchaField, 'clean', Mock())
    def test_with_autoresponse(self):
        """Test contacts for functional area with autoresponses"""
        self.data.update(interest='support')
        self.client.post(self.url_en, self.data)
        eq_(len(mail.outbox), 2)

        cc = ['jay@jaygarcia.com', 'rardila@mozilla.com', 'madasan@gmail.com']
        m = mail.outbox[0]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, ['contribute@mozilla.org'])
        eq_(m.cc, cc)
        eq_(m.extra_headers['Reply-To'], self.contact)

        m = mail.outbox[1]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, [self.contact])
        eq_(m.cc, [])
        eq_(m.extra_headers['Reply-To'], ','.join(cc))

    @patch.object(ReCaptchaField, 'clean', Mock())
    @patch('bedrock.mozorg.email_contribute.jingo.render_to_string')
    def test_no_autoresponse_locale(self, render_mock):
        """
        L10N version to test contacts for functional area without autoresponses
        """
        # first value is for send() and 2nd is for autorespond()
        render_mock.side_effect = ['The Dude minds, man!',
                                   TemplateNotFound('coding.txt')]
        self.data.update(interest='coding')
        self.client.post(self.url_pt_br, self.data)
        eq_(len(mail.outbox), 1)

        m = mail.outbox[0]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, ['contribute@mozilla.org'])
        eq_(m.cc, ['envolva-se-mozilla-brasil@googlegroups.com'])
        eq_(m.extra_headers['Reply-To'], self.contact)

    @patch.object(ReCaptchaField, 'clean', Mock())
    @patch('bedrock.mozorg.email_contribute.jingo.render_to_string')
    def test_with_autoresponse_locale(self, render_mock):
        """
        L10N version to test contacts for functional area with autoresponses
        """
        render_mock.side_effect = 'The Dude abides.'
        self.data.update(interest='support')
        self.client.post(self.url_pt_br, self.data)
        eq_(len(mail.outbox), 2)

        cc = ['envolva-se-mozilla-brasil@googlegroups.com']
        m = mail.outbox[0]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, ['contribute@mozilla.org'])
        eq_(m.cc, cc)
        eq_(m.extra_headers['Reply-To'], self.contact)

        m = mail.outbox[1]
        eq_(m.from_email, 'contribute-form@mozilla.org')
        eq_(m.to, [self.contact])
        eq_(m.cc, [])
        eq_(m.extra_headers['Reply-To'], ','.join(cc))
