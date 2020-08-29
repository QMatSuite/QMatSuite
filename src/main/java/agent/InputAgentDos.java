/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package agent;

import java.io.IOException;

import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumSummation;
import com.consts.Constants.EnumUnitEnergy;

import core.agent.InputAgent;
import core.agent.WrapperBoolean;
import core.agent.WrapperDouble;
import core.agent.WrapperEnum;
import core.com.error.ShowAlert;

public class InputAgentDos extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -5428429337443927602L;

	public boolean setAdvanced=false;
	
	public WrapperDouble emax;
	public WrapperDouble emin;
	public WrapperDouble estep;
	public WrapperEnum energyUnit;
	
	public WrapperEnum enumSummation;
	public WrapperEnum enumSmearing;
	public WrapperDouble degauss;
	
	//pdos, added in v0.3.0
	public WrapperBoolean boolPdos;
	public WrapperBoolean boolLwrite;
	
	//for compatibility 
	private void readObject(java.io.ObjectInputStream in)throws IOException, ClassNotFoundException 
	{
		//for default loading after serialization
	    in.defaultReadObject();
	    //pdos, added in v0.3.0
	    if(boolLwrite==null) {boolLwrite=new WrapperBoolean(false);
	    	//ShowAlert.showAlert("Debug", "boolLwrite here");
	    }
	    if(boolPdos==null) {boolPdos=new WrapperBoolean(false);}
	}
	public InputAgentDos() {
		emax = new WrapperDouble(null);
		emin = new WrapperDouble(null);
		estep = new WrapperDouble(0.1);
		energyUnit = new WrapperEnum(EnumUnitEnergy.eV);
		
		enumSummation = new WrapperEnum(EnumSummation.from_input);
		enumSmearing = new WrapperEnum(EnumSmearing.gauss);
		degauss = new WrapperDouble(null);
		
		//pdos
		boolLwrite=new WrapperBoolean(false);
		boolPdos=new WrapperBoolean(false);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
