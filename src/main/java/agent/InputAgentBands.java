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

import java.util.ArrayList;

import com.consts.Constants.EnumKUnitBands;

import app.input.Kpoint;


public class InputAgentBands extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3123568374548375634L;
	public WrapperEnum enumKUnit;
	public WrapperInteger intNBands;
	public ArrayList<Kpoint> listKPoints;
	
	public InputAgentBands() {
		enumKUnit = new WrapperEnum(EnumKUnitBands.crystal_b);
		intNBands = new WrapperInteger(null);
		listKPoints = new ArrayList<Kpoint>();
	}
}
