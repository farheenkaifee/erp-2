#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""This file is part of the django ERP project.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

__author__ = 'Emanuele Bertoldi <emanuele.bertoldi@gmail.com>'
__copyright__ = 'Copyright (c) 2013-2014, django ERP Team'
__version__ = '0.0.5'

from django.test import TestCase
from django.test.client import RequestFactory
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from djangoerp.core.models import Permission, ObjectPermission

from ..models import *
from ..views import *

# Not in public API.
from ..views import _get_content_type_by, _get_object_by, \
                    _get_object_view_perm, _get_object, _get_notification

class GetterFunctionsTestCase(TestCase):
    def setUp(self):                    
        class _FakeRequest(object):    
            def build_absolute_uri(self):
                return "/"
                
            def get_full_path(self):
                return "/"
                
        self.request = _FakeRequest()
        self.request.user, n = get_user_model().objects.get_or_create(username="u")
        
    def test__get_content_type_by_model_name(self):
        """Tests "_get_content_type_by" function.
        """
        user_model = get_user_model()
        
        self.assertEqual(_get_content_type_by("user").model_class(), user_model)
        self.assertEqual(_get_content_type_by("users").model_class(), user_model)
        
        class User(user_model):
            class Meta:
                proxy = True
        
        self.assertEqual(_get_content_type_by("user").model_class(), user_model)
        self.assertEqual(_get_content_type_by("users").model_class(), user_model)
        
    def test_get_object_by_name_and_id(self):
        """Tests "_get_object_by" function.
        """
        user_model = get_user_model()
        
        self.assertEqual(_get_object_by("user", self.request.user.pk), self.request.user)
        
    def test_get_object_view_perm(self):
        """Tests "_get_object_view_perm" function.
        """
        self.assertEqual(_get_object_view_perm(self.request, object_model="user"), "core.view_user")
        
    def test_get_object(self):
        """Tests "_get_object" function.
        """
        self.assertEqual(_get_object(self.request, object_model="user", object_id=self.request.user.pk), self.request.user)
        
    def test_get_notification(self):
        """Tests "_get_notification" function.
        """
        s, n = Signature.objects.get_or_create(slug="custom.signature")
        nt, n = Notification.objects.get_or_create(title="Test", target=self.request.user, signature=s)
        
        self.assertEqual(_get_notification(self.request, pk=nt.pk), nt)
        
class ObjectFollowViewTestCase(TestCase):
    def setUp(self):            
        self.factory = RequestFactory()
        
        user_model = get_user_model()
        
        self.obj = user_model.objects.create(username="u1")
        self.u2 = user_model.objects.create(username="u2")
        self.u3 = user_model.objects.create(username="u3")
        self.op, n = ObjectPermission.objects.get_or_create_by_uid("core.view_user.%d" % self.obj.pk)
        self.op.users.add(self.u2)
        
    def test_adding_new_follower(self):
        """Tests adding a new follower.
        """
        # Reset followers.
        self.obj.remove_followers(self.obj.followers())
        
        view_kwargs = {"object_model": "user", "object_id": self.obj.pk}
        
        request = self.factory.get(reverse("object_follow", kwargs=view_kwargs))
        
        # With invalid follower.
        request.user = self.u3
        
        response = object_follow(request, **view_kwargs)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.obj.is_followed_by(self.u3))
        self.assertEqual(response.url, reverse("user_login")[:-1] + "?next=%s" % request.get_full_path())
        
        # With valid follower.
        request.user = self.u2
        request.META["HTTP_REFERER"] = "/success-redirect"
        
        response = object_follow(request, **view_kwargs)
        
        self.assertTrue(self.obj.is_followed_by(self.u2))
        self.assertEqual(response.url, "/success-redirect")
        
class ObjectUnfollowViewTestCase(TestCase):
    def setUp(self):            
        self.factory = RequestFactory()
        
        user_model = get_user_model()
        
        self.obj = user_model.objects.create(username="u1")
        self.u2 = user_model.objects.create(username="u2")
        self.u3 = user_model.objects.create(username="u3")
        self.op, n = ObjectPermission.objects.get_or_create_by_uid("core.view_user.%d" % self.obj.pk)
        self.op.users.add(self.u2)
        
    def test_adding_new_follower(self):
        """Tests removing a follower.
        """
        # Reset followers.
        self.obj.remove_followers(self.obj.followers())
        
        self.obj.add_followers(self.u2)
        
        view_kwargs = {"object_model": "user", "object_id": self.obj.pk}
        
        request = self.factory.get(reverse("object_unfollow", kwargs=view_kwargs))
        
        # With invalid follower.
        request.user = self.u3
        
        self.assertFalse(self.obj.is_followed_by(self.u3))
        
        response = object_unfollow(request, **view_kwargs)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.obj.is_followed_by(self.u3))
        self.assertEqual(response.url, reverse("user_login")[:-1] + "?next=%s" % request.get_full_path())
        
        # With valid follower.
        request.user = self.u2
        request.META["HTTP_REFERER"] = "/success-redirect"
        
        self.assertTrue(self.obj.is_followed_by(self.u2))
        
        response = object_unfollow(request, **view_kwargs)
        
        self.assertFalse(self.obj.is_followed_by(self.u2))
        self.assertEqual(response.url, "/success-redirect")
        
class ListNotificationViewTestCase(TestCase):
    def test_permissions(self):
        """Tests view's permissions.
        """        
        user_model = get_user_model()
        
        obj = user_model.objects.create(username="u1")
        
        u2 = user_model.objects.create_user(username="u2", email="u2@u.it", password="p")
        u3 = user_model.objects.create_user(username="u3", email="u3@u.it", password="p")
        
        vp, n = Permission.objects.get_or_create_by_uid("notifications.view_notification")
        op, n = ObjectPermission.objects.get_or_create_by_uid("core.view_user.%d" % obj.pk)
        op.users.add(u2)
        u2.user_permissions.add(vp)
        
        obj.add_followers(u2)
        
        url = reverse('notification_list', kwargs={"object_model": "user", "object_id": obj.pk})
        
        # With invalid follower.
        self.assertFalse(obj.is_followed_by(u3))
        
        self.client.login(username="u3", password="p")
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(obj.is_followed_by(u3))
        self.assertEqual(response.url, "http://testserver" + reverse("user_login")[:-1] + "?next=%s" % url)
        
        # With valid follower.
        self.assertTrue(obj.is_followed_by(u2))
        
        self.client.login(username="u2", password="p")
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)