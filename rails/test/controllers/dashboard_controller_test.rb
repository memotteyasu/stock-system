require "test_helper"

class DashboardControllerTest < ActionDispatch::IntegrationTest
  setup do
    @previous_username = ENV["ADMIN_USERNAME"]
    @previous_password = ENV["ADMIN_PASSWORD"]
    ENV["ADMIN_USERNAME"] = "test-admin"
    ENV["ADMIN_PASSWORD"] = "test-password"
  end

  teardown do
    ENV["ADMIN_USERNAME"] = @previous_username
    ENV["ADMIN_PASSWORD"] = @previous_password
  end

  test "dashboard requires administrator authentication" do
    get root_path

    assert_response :unauthorized
    assert_equal 'Basic realm="Stock Monitor"', response.headers["WWW-Authenticate"]
  end

  test "dashboard rejects invalid administrator authentication" do
    get root_path, headers: {
      "Authorization" => ActionController::HttpAuthentication::Basic.encode_credentials(
        "test-admin", "invalid-password"
      )
    }

    assert_response :unauthorized
  end
end
