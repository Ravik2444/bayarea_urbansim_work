import urbansim.sim.simulation as sim
from urbansim.utils import misc
import os
import datasources
# import variables
from urbansim import accounts
from urbansim_defaults import models
from urbansim_defaults import utils


@sim.injectable("supply_and_demand_multiplier_func", autocall=False)
def supply_and_demand_multiplier_func(demand, supply):
    s = demand / supply
    settings = sim.get_injectable("settings")
    print "Number of submarkets where demand exceeds supply:", len(s[s>1.0])
    print "Raw relationship of supply and demand\n", s.describe()
    supply_correction = settings["enable_supply_correction"]
    clip_change_high = supply_correction["kwargs"]["clip_change_high"]
    t = s
    t -= 1.0
    t = t / t.max() * (clip_change_high-1)
    t += 1.0
    s.loc[s > 1.0] = t.loc[s > 1.0]
    print "Shifters for current iteration\n", s.describe()
    return s, (s <= 1.0).all()


# this if the function for mapping a specific building that we build to a
# specific building type
@sim.injectable("form_to_btype_f", autocall=False)
def form_to_btype_f(building):
    settings = sim.get_injectable("settings")
    form = building.form
    dua = building.residential_units / (building.parcel_size / 43560.0)
    # precise mapping of form to building type for residential
    if form == "residential":
        if dua < 16:
            return 1
        elif dua < 32:
            return 2
        return 3
    return settings["form_to_btype"][form][0]


@sim.injectable("coffer")
def coffer():
    return {
        "prop_tax_acct": accounts.Account("prop_tax_act")
    }


@sim.model("calc_prop_taxes")
def property_taxes(parcels, settings, coffer, year):
    # TODO might want to filter on only commercial buildings
    tax = parcels.building_purchase_price * \
        settings["acct_settings"]["prop_tax_rate"]
    # TODO group by county_id
    tot_tax_by_city = tax.groupby(parcels.county_id).sum()
    for city_id, amt in tot_tax_by_city.iteritems():
        coffer["prop_tax_acct"].add_transaction(amt, subaccount=city_id,
                                                meta_data={
                                                    "year": year
                                                })
    print "Current property tax accounting:"
    print coffer["prop_tax_acct"].to_frame().describe()


@sim.model("travel_model_output")
def travel_model_output(parcels, households, jobs, buildings, 
                        zones, homesales, year):
    households = households.to_frame()
    jobs = jobs.to_frame()
    buildings = buildings.to_frame()
    zones = zones.to_frame()
    homesales = homesales.to_frame()

    # put this here as a custom bay area indicator
    zones['residential_sales_price_empirical'] = homesales.groupby('zone_id').\
        sale_price_flt.quantile()
    zones['residential_sales_price_sqft'] = parcels.\
        residential_sales_price_sqft.groupby(parcels.zone_id).quantile()
    zones['residential_purchase_price_sqft'] = parcels.\
        residential_purchase_price_sqft.groupby(parcels.zone_id).quantile()
    if 'residential_price_hedonic' in buildings.columns:
        zones['residential_sales_price_hedonic'] = buildings.\
            residential_price_hedonic.\
            groupby(buildings.zone_id).quantile().\
            reindex(zones.index).fillna(0)
    else: 
        zones['residential_sales_price_hedonic'] = 0

    zones['tothh'] = households.\
        groupby('zone_id').size()
    zones['hhpop'] = households.\
        groupby('zone_id').persons.sum()

    zones['sfdu'] = \
        buildings.query("building_type_id == 1 or building_type_id == 2").\
        groupby('zone_id').residential_units.sum()
    zones['mfdu'] = \
        buildings.query("building_type_id == 3 or building_type_id == 12").\
        groupby('zone_id').residential_units.sum()

    zones['hhincq1'] = households.query("income < 25000").\
        groupby('zone_id').size()
    zones['hhincq2'] = households.query("income >= 25000 and income < 45000").\
        groupby('zone_id').size()
    zones['hhincq3'] = households.query("income >= 45000 and income < 75000").\
        groupby('zone_id').size()
    zones['hhincq4'] = households.query("income >= 75000").\
        groupby('zone_id').size()

    # attempting to get at total zonal developed acres
    zones['NEWdevacres'] = \
        (buildings.query("building_sqft > 0").
         groupby('zone_id').lot_size_per_unit.sum()) / 43560

    zones['totemp'] = jobs.\
        groupby('zone_id').size()
    zones['agrempn'] = jobs.query("empsix == 'AGREMPN'").\
        groupby('zone_id').size()
    zones['mwtempn'] = jobs.query("empsix == 'MWTEMPN'").\
        groupby('zone_id').size()
    zones['retempn'] = jobs.query("empsix == 'RETEMPN'").\
        groupby('zone_id').size()
    zones['fpsempn'] = jobs.query("empsix == 'FPSEMPN'").\
        groupby('zone_id').size()
    zones['herempn'] = jobs.query("empsix == 'HEREMPN'").\
        groupby('zone_id').size()
    zones['othempn'] = jobs.query("empsix == 'OTHEMPN'").\
        groupby('zone_id').size()

    sim.add_table("travel_model_output", zones, year)

    utils.add_simulation_output(zones, "travel_model_outputs", year)
    utils.write_simulation_output(os.path.join(misc.runs_dir(),
                                               "run{}_simulation_output.json"))
    utils.write_parcel_output(os.path.join(misc.runs_dir(),
                                           "run{}_parcel_output.csv"))

