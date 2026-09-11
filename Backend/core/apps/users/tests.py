from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class UserViewSetPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="x", phone="1111111111", role=User.Role.ADMIN,
        )
        self.analyst = User.objects.create_user(
            email="analyst@example.com", password="x", phone="2222222222", role=User.Role.DATA_ANALYST,
        )
        self.client = APIClient()

    def test_admin_can_list_users(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_non_admin_cannot_list_users(self):
        self.client.force_authenticate(user=self.analyst)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/users/", {
            "first_name": "New", "last_name": "Hire", "email": "new@example.com",
            "phone": "3333333333", "role": User.Role.DATA_ENGINEER, "password": "hunter2pass",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        created = User.objects.get(email="new@example.com")
        self.assertTrue(created.check_password("hunter2pass"))
        self.assertEqual(created.role, User.Role.DATA_ENGINEER)

    def test_create_without_password_fails(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/users/", {
            "first_name": "No", "last_name": "Pass", "email": "nopass@example.com",
            "phone": "4444444444", "role": User.Role.DATA_ANALYST,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_admin_can_update_and_delete_user(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(f"/api/users/{self.analyst.id}/", {
            "role": User.Role.ADMIN,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.analyst.refresh_from_db()
        self.assertEqual(self.analyst.role, User.Role.ADMIN)

        response = self.client.delete(f"/api/users/{self.analyst.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(id=self.analyst.id).exists())

    def test_unauthenticated_cannot_access(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 401)
