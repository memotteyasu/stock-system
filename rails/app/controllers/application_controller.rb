require "digest"

class ApplicationController < ActionController::Base
  # Only allow modern browsers supporting webp images, web push, badges, import maps, CSS nesting, and CSS :has.
  allow_browser versions: :modern

  protect_from_forgery with: :exception

  before_action :authenticate_admin!

  private

  def authenticate_admin!
    authenticate_or_request_with_http_basic("Stock Monitor") do |username, password|
      expected_username = ENV["ADMIN_USERNAME"]
      expected_password = ENV["ADMIN_PASSWORD"]

      expected_username.present? &&
        expected_password.present? &&
        secure_credential_match?(username, expected_username) &&
        secure_credential_match?(password, expected_password)
    end
  end

  def secure_credential_match?(provided, expected)
    ActiveSupport::SecurityUtils.secure_compare(
      Digest::SHA256.hexdigest(provided),
      Digest::SHA256.hexdigest(expected)
    )
  end
end
