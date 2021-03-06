import pyramid.httpexceptions as http
import pytest
import sqlalchemy.orm.exc as orm_exc

from auth_app.models import User, Session
from auth_app.forms import CreateUserForm


pytestmark = [
    pytest.mark.unit,
    pytest.mark.views,
    pytest.mark.admin,
    pytest.mark.usefixtures("rollback")
]


def test_get_manage_user(test_config, alembic_head):
    """ UserManagementViews.manage_users returns users list """
    from auth_app.views.admin import UserManagementViews

    all_users = User.all()

    request = test_config.DummyRequest()
    response = UserManagementViews(request).manage_users()

    assert "users" in response
    assert response["users"] == all_users


def test_get_manage_user_show_create_user_form(test_config, alembic_head):
    """ UserManagementViews.manage_users has the CreateUserForm """
    from auth_app.views.admin import UserManagementViews

    request = test_config.DummyRequest()
    response = UserManagementViews(request).manage_users()

    assert "create_user_form" in response
    assert isinstance(response["create_user_form"], CreateUserForm)
    assert len(response["create_user_form"].errors) == 0


def test_create_user_redirects(test_config, alembic_head, new_user_kwargs):
    """ UserManagementViews.create_user redirects """
    from auth_app.views.admin import UserManagementViews

    request = test_config.DummyRequest(params=new_user_kwargs)
    response = UserManagementViews(request).create_user()

    assert isinstance(response, http.HTTPFound)


def test_create_user_makes_user(test_config, alembic_head, new_user_kwargs):
    """ UserManagementViews.create_user inserts new user into DB """
    from auth_app.views.admin import UserManagementViews

    # just make sure the new_user isn't already in the DB
    results = User.all(email=new_user_kwargs['email'])
    assert len(results) == 0

    request = test_config.DummyRequest(post=new_user_kwargs)
    UserManagementViews(request).create_user()

    new_user = User.one(email=new_user_kwargs['email'])
    assert new_user.email == new_user_kwargs['email']
    assert new_user.user_type == new_user_kwargs['user_type']


def test_create_user_email_unique(test_config, alembic_head, new_user_kwargs,
                                  test_user):
    """ UserManagementViews.create_user fails w/ non-unique email address """
    from auth_app.views.admin import UserManagementViews

    new_user_kwargs['email'] = test_user.email

    count = len(User.all())

    request = test_config.DummyRequest(params=new_user_kwargs)
    response = UserManagementViews(request).create_user()

    assert len(User.all()) == count
    assert len(response['create_user_form'].errors) > 0


@pytest.mark.parametrize("missing_kwargs", ["email"])
def test_create_user_required_arguments(test_config, alembic_head,
                                        new_user_kwargs, missing_kwargs):
    """ UserManagementViews.create_user fails when missing required values """
    from auth_app.views.admin import UserManagementViews

    count = len(User.all())

    new_user_kwargs.pop(missing_kwargs)

    request = test_config.DummyRequest(params=new_user_kwargs)
    response = UserManagementViews(request).create_user()

    assert len(User.all()) == count
    assert len(response['create_user_form'].errors) > 0


def test_delete_user(test_user, test_config):
    """ UserManagementViews.delete_user removes user from DB """
    from auth_app.views.admin import UserManagementViews

    request = test_config.DummyRequest()
    request.context = User.one(user_id=test_user.user_id)

    count = len(User.all())

    UserManagementViews(request).delete_user()

    with pytest.raises(orm_exc.NoResultFound):
        assert User.one(user_id=test_user.user_id)
    assert count - 1 == len(User.all())


def test_delete_nonexistant_user(test_config):
    """ UserManagementViews.delete_user fails w/ nonexistant user """
    from auth_app.views.admin import UserManagementViews

    request = test_config.DummyRequest()
    request.context = None

    count = len(User.all())

    with pytest.raises(orm_exc.UnmappedInstanceError):
        UserManagementViews(request).delete_user()

    assert count == len(User.all())


def test_reset_user_sets_token(test_config, test_user):
    """ UserManagementViews.reset_user sets token """
    from auth_app.views.admin import UserManagementViews

    user = User.one(user_id=test_user.user_id)

    request = test_config.DummyRequest()
    request.context = user

    UserManagementViews(request).reset_user()

    Session.refresh(user)
    assert user.token != test_user.token
    assert user.token is not None


def test_reset_user_changes_password(test_config, test_user):
    """ UserManagementViews.reset_user changes password """
    from auth_app.views.admin import UserManagementViews

    user = User.one(user_id=test_user.user_id)

    request = test_config.DummyRequest()
    request.context = user

    UserManagementViews(request).reset_user()

    Session.refresh(user)
    assert user.validate(test_user._unhashed_password) is False


def test_reset_user_redirects_to_user_management(test_config, test_user):
    """ UserManagementViews.reset_user returns HTTPFound """
    from auth_app.views.admin import UserManagementViews

    user = User.one(user_id=test_user.user_id)

    request = test_config.DummyRequest()
    request.context = user

    response = UserManagementViews(request).reset_user()
    assert isinstance(response, http.HTTPFound)
    assert response.location == request.route_url('manage_users')
