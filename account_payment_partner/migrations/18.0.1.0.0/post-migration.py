# Copyright 2025 Le Filament (https://le-filament.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _migrate_custom_company_dependent_field(
    env, model_name, field_name, value_expression=None
):
    # Logic from openupgrade_180.convert_company_dependent
    Model = env[model_name]
    Field = env["ir.model.fields"]._get(model_name, field_name)

    value_expression = value_expression or (
        "value_%s"
        % {
            "float": "float",
            "boolean": "integer",
            "integer": "integer",
            "date": "datetime",
            "datetime": "datetime",
        }.get(Field.ttype, "text")
        if Field.ttype != "many2one"
        else "SPLIT_PART(value_reference, ',', 2)::integer"
    )

    openupgrade.logged_query(
        env.cr,
        f"ALTER TABLE {Model._table} ADD COLUMN IF NOT EXISTS {field_name} jsonb",
    )

    # Change ir_property into _ir_property
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE {Model._table} SET {field_name} = ir_property_by_company.value
        FROM (
            SELECT
                SPLIT_PART(res_id, ',', 2)::integer AS res_id,
                JSON_OBJECT_AGG(company_id, {value_expression}) AS "value"
            FROM _ir_property
            WHERE
                fields_id = {Field.id} AND res_id IS NOT NULL
                AND company_id IS NOT NULL
            GROUP BY 1
        ) ir_property_by_company
        WHERE {Model._table}.id = ir_property_by_company.res_id
        """,
    )

    # Change ir_property into _ir_property
    env.cr.execute(
        f"""
        SELECT company_id, {value_expression} FROM _ir_property
        WHERE
            fields_id = {Field.id} AND res_id IS NULL
        """
    )
    for company_id, value in env.cr.fetchall():
        if value:
            env["ir.default"].set(model_name, field_name, value, company_id=company_id)


@openupgrade.migrate()
def migrate(env, version):
    _migrate_custom_company_dependent_field(
        env, "res.partner", "supplier_payment_mode_id"
    )
    _migrate_custom_company_dependent_field(
        env, "res.partner", "customer_payment_mode_id"
    )
