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

import com.consts.Constants.EnumExtrapolation;
import com.consts.Constants.EnumPolarizability;
import com.consts.Constants.EnumTddftUnitEnergy;

import core.agent.InputAgent;

public class InputAgentTddft extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3123568374548375634L;
	
	public WrapperInteger itermax0;//from turbo_lanczos.x, and number of coefficients read in turbo_spectrum.x
	public WrapperEnum enumPolar;
	public WrapperInteger itermax;//for turbo_spectrum.x
	public WrapperEnum enumExtrap;
	public WrapperEnum enumEUnit;
	public WrapperDouble epsil,
	estart,
	eend,
	de;
	public WrapperBoolean eels;
	
	
	public InputAgentTddft() {
		itermax0 =  new WrapperInteger(500);
		enumPolar = new WrapperEnum(EnumPolarizability.alpha_xx);
		itermax =  new WrapperInteger(500);
		enumExtrap = new WrapperEnum(EnumExtrapolation.no);
		enumEUnit = new WrapperEnum(EnumTddftUnitEnergy.Ry);
		epsil = new WrapperDouble(0.02);//in Ry
		estart = new WrapperDouble(0.0);
		eend = new WrapperDouble(2.5);
		de = new WrapperDouble(0.001);
		eels =  new WrapperBoolean(false);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
