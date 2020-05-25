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

import com.consts.Constants.enumInProgram;

public class WrapperEnum extends WrapperClass{
	/**
	 * 
	 */
	private static final long serialVersionUID = -5526687023913245151L;
	private enumInProgram value;
	public WrapperEnum(enumInProgram val) {
		value = val;
		enabled = true;
	}
	public WrapperEnum(enumInProgram val,Boolean bl) {
		value = val;
		enabled = bl;
	}
	public enumInProgram getValue() {
		return value;
	}
	public void setValue(enumInProgram val) {
		value = val;
	}
	public Boolean equals(enumInProgram vl) {
		return vl==value;
	}
	@Override
	public Boolean isNull() {
		return value==null;
	}
}